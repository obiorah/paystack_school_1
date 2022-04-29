import frappe,json
from six import iteritems, string_types
from frappe import _
from frappe import ValidationError, _, scrub, throw
from frappe.integrations.utils import get_payment_gateway_controller
from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request
from frappe.utils.csvutils import getlink
from erpnext.setup.utils import get_exchange_rate
from frappe.utils import get_url
from erpnext.controllers.accounts_controller import (
	AccountsController,
	get_supplier_block_status,
	validate_taxes_and_charges,
)
def split_invoices_based_on_payment_terms(outstanding_invoices):
	invoice_ref_based_on_payment_terms = {}
	for idx, d in enumerate(outstanding_invoices):
		if d.voucher_type in ["Sales Invoice", "Purchase Invoice"]:
			payment_term_template = frappe.db.get_value(
				d.voucher_type, d.voucher_no, "payment_terms_template"
			)
			if payment_term_template:
				allocate_payment_based_on_payment_terms = frappe.db.get_value(
					"Payment Terms Template", payment_term_template, "allocate_payment_based_on_payment_terms"
				)
				if allocate_payment_based_on_payment_terms:
					payment_schedule = frappe.get_all(
						"Payment Schedule", filters={"parent": d.voucher_no}, fields=["*"]
					)

					for payment_term in payment_schedule:
						if payment_term.outstanding > 0.1:
							invoice_ref_based_on_payment_terms.setdefault(idx, [])
							invoice_ref_based_on_payment_terms[idx].append(
								frappe._dict(
									{
										"due_date": d.due_date,
										"currency": d.currency,
										"voucher_no": d.voucher_no,
										"voucher_type": d.voucher_type,
										"posting_date": d.posting_date,
										"invoice_amount": flt(d.invoice_amount),
										"outstanding_amount": flt(d.outstanding_amount),
										"payment_amount": payment_term.payment_amount,
										"payment_term": payment_term.payment_term,
									}
								)
							)

	outstanding_invoices_after_split = []
	if invoice_ref_based_on_payment_terms:
		for idx, ref in invoice_ref_based_on_payment_terms.items():
			voucher_no = ref[0]["voucher_no"]
			voucher_type = ref[0]["voucher_type"]

			frappe.msgprint(
				_("Spliting {} {} into {} row(s) as per Payment Terms").format(
					voucher_type, voucher_no, len(ref)
				),
				alert=True,
			)

			outstanding_invoices_after_split += invoice_ref_based_on_payment_terms[idx]

			existing_row = list(filter(lambda x: x.get("voucher_no") == voucher_no, outstanding_invoices))
			index = outstanding_invoices.index(existing_row[0])
			outstanding_invoices.pop(index)

	outstanding_invoices_after_split += outstanding_invoices
	return outstanding_invoices_after_split


from frappe.utils import cint, comma_or, flt, getdate, nowdate
from erpnext.accounts.doctype.bank_account.bank_account import (
	get_bank_account_details,
	get_party_bank_account,
)
from erpnext.accounts.doctype.invoice_discounting.invoice_discounting import (
	get_party_account_based_on_invoice_discounting,
)
from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account

from erpnext.accounts.party import get_party_account
from erpnext.accounts.utils import get_account_currency, get_balance_on, get_outstanding_invoices
from functools import reduce
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_company_defaults,get_account_details
)

def get_payment_gateway_url(self, doc):
    if self.accept_payment:
        controller = get_payment_gateway_controller(self.payment_gateway)

        title = "Payment for {0} {1}".format(doc.doctype, doc.name)
        name = doc.name
        amount = self.amount
        if frappe.session.user == "Guest" or "Administrator":
            email = doc.student_email_id
        else:
            email = frappe.session.user
        fullname = doc.first_name + ' ' + doc.middle_name + ' ' + doc.last_name
        if not doc.middle_name and doc.last_name:
            fullname = doc.first_name
        if self.amount_based_on_field:
            amount = doc.get(self.amount_field)

        from decimal import Decimal
        if amount is None or Decimal(amount) <= 0:
            return frappe.utils.get_url(self.success_url or self.route)

        reference_doctype = "Web Form"
        reference_docname = self.name
        # get_doctype for the web_form
        if self.doc_type == "Student Applicant":
            # create a fees scheudle for the student, which will be used as reference in the integration request
            reference_doctype = self.doc_type
            reference_docname = doc.name
        payment_details = {
            "amount": amount,
            "title": title,
            "description": title,
            "docname":name,
            "reference_doctype": reference_doctype,
            "reference_docname": reference_docname,
            "payer_email": email,
            "payer_name": fullname,
            "order_id": doc.name,
            "currency": self.currency,
            "redirect_to": frappe.utils.get_url(self.success_url or self.route)
        }

        # Redirect the user to this url
        return controller.get_payment_url(**payment_details)




def on_submit(self):

    self.make_gl_entries()

    if self.send_payment_request and self.student_email:
        party_type = self.fee_document_type
        pr = make_payment_request(
            party_type=party_type,
            party=self.student,
            dt="Fees",
            dn=self.name,
            recipient_id=self.student_email,
            submit_doc=True,
            use_dummy_message=True,
        )
        frappe.msgprint(_("Payment request {0} created").format(getlink("Payment Request", pr.name)))

def make_gl_entries(self):
    if not self.grand_total:
        return
    party_type = self.fee_document_type
    student_gl_entries = self.get_gl_dict(
        {
            "account": self.receivable_account,
            "party_type": party_type,
            "party": self.student,
            "against": self.income_account,
            "debit": self.grand_total,
            "debit_in_account_currency": self.grand_total,
            "against_voucher": self.name,
            "against_voucher_type": self.doctype,
        },
        item=self,
    )

    fee_gl_entry = self.get_gl_dict(
        {
            "account": self.income_account,
            "against": self.student,
            "credit": self.grand_total,
            "credit_in_account_currency": self.grand_total,
            "cost_center": self.cost_center,
        },
        item=self,
    )

    from erpnext.accounts.general_ledger import make_gl_entries

    make_gl_entries(
        [student_gl_entries, fee_gl_entry],
        cancel=(self.docstatus == 2),
        update_outstanding="Yes",
        merge_entries=False,
    )


def get_payment_entry(dt, dn, party_amount=None, bank_account=None, bank_amount=None):
    reference_doc = None
    doc = frappe.get_doc(dt, dn)
    if dt in ("Sales Order", "Purchase Order") and flt(doc.per_billed, 2) > 0:
        frappe.throw(_("Can only make payment against unbilled {0}").format(dt))

    party_type = get_party_type(dt,doc)
    party_account = set_party_account(dt, dn, doc, party_type)
    party_account_currency = set_party_account_currency(dt, party_account, doc)
    payment_type = set_payment_type(dt, doc)
    grand_total, outstanding_amount = set_grand_total_and_outstanding_amount(
    party_amount, dt, party_account_currency, doc
    )

    # bank or cash
    bank = get_bank_cash_account(doc, bank_account)

    paid_amount, received_amount = set_paid_amount_and_received_amount(
        dt, party_account_currency, bank, outstanding_amount, payment_type, bank_amount, doc
    )

    paid_amount, received_amount, discount_amount = apply_early_payment_discount(
        paid_amount, received_amount, doc
    )
    party = doc.get(scrub(party_type))
    if not party:
        # get party from doctype directly
        party = frappe.db.get_value('Payment Request',{'reference_doctype':dt,'reference_name':dn},'party')
    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = payment_type
    pe.company = doc.company
    pe.cost_center = doc.get("cost_center")
    pe.posting_date = nowdate()
    pe.mode_of_payment = doc.get("mode_of_payment")
    pe.party_type = party_type
    pe.party = party
    pe.contact_person = doc.get("contact_person")
    pe.contact_email = doc.get("contact_email")
    pe.ensure_supplier_is_not_blocked()

    pe.paid_from = party_account if payment_type == "Receive" else bank.account
    pe.paid_to = party_account if payment_type == "Pay" else bank.account
    pe.paid_from_account_currency = (
    party_account_currency if payment_type == "Receive" else bank.account_currency
    )
    pe.paid_to_account_currency = (
    party_account_currency if payment_type == "Pay" else bank.account_currency
    )
    pe.paid_amount = paid_amount
    pe.received_amount = received_amount
    pe.letter_head = doc.get("letter_head")

    if dt in ["Purchase Order", "Sales Order", "Sales Invoice", "Purchase Invoice"]:
        pe.project = doc.get("project") or reduce(
            lambda prev, cur: prev or cur, [x.get("project") for x in doc.get("items")], None
        )  # get first non-empty project from items

    if pe.party_type in ["Customer", "Supplier"]:
        bank_account = get_party_bank_account(pe.party_type, pe.party)
        pe.set("bank_account", bank_account)
        pe.set_bank_account_data()

	# only Purchase Invoice can be blocked individually
    if doc.doctype == "Purchase Invoice" and doc.invoice_is_blocked():
        frappe.msgprint(_("{0} is on hold till {1}").format(doc.name, doc.release_date))
    else:
        if doc.doctype in ("Sales Invoice", "Purchase Invoice") and frappe.get_value(
			"Payment Terms Template",
			{"name": doc.payment_terms_template},
			"allocate_payment_based_on_payment_terms",
		):

            for reference in get_reference_as_per_payment_terms(
                doc.payment_schedule, dt, dn, doc, grand_total, outstanding_amount
            ):
                pe.append("references", reference)
        else:
            if dt == "Dunning":
                pe.append(
                    "references",
                    {
                    "reference_doctype": "Sales Invoice",
                    "reference_name": doc.get("sales_invoice"),
                    "bill_no": doc.get("bill_no"),
                    "due_date": doc.get("due_date"),
                    "total_amount": doc.get("outstanding_amount"),
                    "outstanding_amount": doc.get("outstanding_amount"),
                    "allocated_amount": doc.get("outstanding_amount"),
                    },
                )
                pe.append(
                    "references",
                    {
                    "reference_doctype": dt,
                    "reference_name": dn,
                    "bill_no": doc.get("bill_no"),
                    "due_date": doc.get("due_date"),
                    "total_amount": doc.get("dunning_amount"),
                    "outstanding_amount": doc.get("dunning_amount"),
                    "allocated_amount": doc.get("dunning_amount"),
                    },
                )
            else:
                pe.append(
					"references",
					{
						"reference_doctype": dt,
						"reference_name": dn,
						"bill_no": doc.get("bill_no"),
						"due_date": doc.get("due_date"),
						"total_amount": grand_total,
						"outstanding_amount": outstanding_amount,
						"allocated_amount": outstanding_amount,
					},
				)

    pe.setup_party_account_field()
    pe.set_missing_values()

    if party_account and bank:
        if dt == "Employee Advance":
            reference_doc = doc
            pe.set_exchange_rate(ref_doc=reference_doc)
            pe.set_amounts()

        if discount_amount:
            pe.set_gain_or_loss(
                account_details={
                    "account": frappe.get_cached_value("Company", pe.company, "default_discount_account"),
                    "cost_center": pe.cost_center
                    or frappe.get_cached_value("Company", pe.company, "cost_center"),
                    "amount": discount_amount * (-1 if payment_type == "Pay" else 1),
                }
            )
            pe.set_difference_amount()
    return pe


def get_party_type(dt,doc):
	try:
		fee_document_type = doc.fee_document_type
	except:
		pass
	if dt in ("Sales Invoice", "Sales Order", "Dunning"):
		party_type = "Customer"
	elif dt in ("Purchase Invoice", "Purchase Order"):
		party_type = "Supplier"
	elif fee_document_type == 'Student Applicant':
		party_type = "Student Applicant"
	elif fee_document_type == 'Student Applicant':
		party_type = "Student"
	elif dt in ("Expense Claim", "Employee Advance", "Gratuity"):
		party_type = "Employee"
	elif dt == "Fees":
		party_type = "Student"
	elif dt == "Donation":
		party_type = "Donor"

	return party_type


def set_party_account(dt, dn, doc, party_type):
    if dt == "Sales Invoice":
        party_account = get_party_account_based_on_invoice_discounting(dn) or doc.debit_to
    elif dt == "Purchase Invoice":
        party_account = doc.credit_to
    elif dt == "Fees":
        party_account = doc.receivable_account
    elif dt == "Employee Advance":
        party_account = doc.advance_account
    elif dt == "Expense Claim":
        party_account = doc.payable_account
    elif dt == "Gratuity":
        party_account = doc.payable_account
    else:
        party_account = get_party_account(party_type, doc.get(party_type.lower()), doc.company)
    return party_account


def set_party_account_currency(dt, party_account, doc):
    if dt not in ("Sales Invoice", "Purchase Invoice"):
        party_account_currency = get_account_currency(party_account)
    else:
        party_account_currency = doc.get("party_account_currency") or get_account_currency(party_account)
    return party_account_currency


def set_payment_type(dt, doc):
	if (
		dt in ("Sales Order", "Donation")
		or (dt in ("Sales Invoice", "Fees", "Dunning") and doc.outstanding_amount > 0)
	) or (dt == "Purchase Invoice" and doc.outstanding_amount < 0):
		payment_type = "Receive"
	else:
		payment_type = "Pay"
	return payment_type


def set_grand_total_and_outstanding_amount(party_amount, dt, party_account_currency, doc):
	grand_total = outstanding_amount = 0
	if party_amount:
		grand_total = outstanding_amount = party_amount
	elif dt in ("Sales Invoice", "Purchase Invoice"):
		if party_account_currency == doc.company_currency:
			grand_total = doc.base_rounded_total or doc.base_grand_total
		else:
			grand_total = doc.rounded_total or doc.grand_total
		outstanding_amount = doc.outstanding_amount
	elif dt in ("Expense Claim"):
		grand_total = doc.total_sanctioned_amount + doc.total_taxes_and_charges
		outstanding_amount = doc.grand_total - doc.total_amount_reimbursed
	elif dt == "Employee Advance":
		grand_total = flt(doc.advance_amount)
		outstanding_amount = flt(doc.advance_amount) - flt(doc.paid_amount)
		if party_account_currency != doc.currency:
			grand_total = flt(doc.advance_amount) * flt(doc.exchange_rate)
			outstanding_amount = (flt(doc.advance_amount) - flt(doc.paid_amount)) * flt(doc.exchange_rate)
	elif dt == "Fees":
		grand_total = doc.grand_total
		outstanding_amount = doc.outstanding_amount
	elif dt == "Dunning":
		grand_total = doc.grand_total
		outstanding_amount = doc.grand_total
	elif dt == "Donation":
		grand_total = doc.amount
		outstanding_amount = doc.amount
	elif dt == "Gratuity":
		grand_total = doc.amount
		outstanding_amount = flt(doc.amount) - flt(doc.paid_amount)
	else:
		if party_account_currency == doc.company_currency:
			grand_total = flt(doc.get("base_rounded_total") or doc.base_grand_total)
		else:
			grand_total = flt(doc.get("rounded_total") or doc.grand_total)
		outstanding_amount = grand_total - flt(doc.advance_paid)
	return grand_total, outstanding_amount


def set_paid_amount_and_received_amount(
	dt, party_account_currency, bank, outstanding_amount, payment_type, bank_amount, doc
):
	paid_amount = received_amount = 0
	if party_account_currency == bank.account_currency:
		paid_amount = received_amount = abs(outstanding_amount)
	elif payment_type == "Receive":
		paid_amount = abs(outstanding_amount)
		if bank_amount:
			received_amount = bank_amount
		else:
			received_amount = paid_amount * doc.get("conversion_rate", 1)
			if dt == "Employee Advance":
				received_amount = paid_amount * doc.get("exchange_rate", 1)
	else:
		received_amount = abs(outstanding_amount)
		if bank_amount:
			paid_amount = bank_amount
		else:
			# if party account currency and bank currency is different then populate paid amount as well
			paid_amount = received_amount * doc.get("conversion_rate", 1)
			if dt == "Employee Advance":
				paid_amount = received_amount * doc.get("exchange_rate", 1)

	return paid_amount, received_amount


def apply_early_payment_discount(paid_amount, received_amount, doc):
	total_discount = 0
	eligible_for_payments = ["Sales Order", "Sales Invoice", "Purchase Order", "Purchase Invoice"]
	has_payment_schedule = hasattr(doc, "payment_schedule") and doc.payment_schedule

	if doc.doctype in eligible_for_payments and has_payment_schedule:
		for term in doc.payment_schedule:
			if not term.discounted_amount and term.discount and getdate(nowdate()) <= term.discount_date:
				if term.discount_type == "Percentage":
					discount_amount = flt(doc.get("grand_total")) * (term.discount / 100)
				else:
					discount_amount = term.discount

				discount_amount_in_foreign_currency = discount_amount * doc.get("conversion_rate", 1)

				if doc.doctype == "Sales Invoice":
					paid_amount -= discount_amount
					received_amount -= discount_amount_in_foreign_currency
				else:
					received_amount -= discount_amount
					paid_amount -= discount_amount_in_foreign_currency

				total_discount += discount_amount

		if total_discount:
			money = frappe.utils.fmt_money(total_discount, currency=doc.get("currency"))
			frappe.msgprint(_("Discount of {} applied as per Payment Term").format(money), alert=1)

	return paid_amount, received_amount, total_discount


def get_reference_as_per_payment_terms(
	payment_schedule, dt, dn, doc, grand_total, outstanding_amount
):
	references = []
	for payment_term in payment_schedule:
		payment_term_outstanding = flt(
			payment_term.payment_amount - payment_term.paid_amount, payment_term.precision("payment_amount")
		)

		if payment_term_outstanding:
			references.append(
				{
					"reference_doctype": dt,
					"reference_name": dn,
					"bill_no": doc.get("bill_no"),
					"due_date": doc.get("due_date"),
					"total_amount": grand_total,
					"outstanding_amount": outstanding_amount,
					"payment_term": payment_term.payment_term,
					"allocated_amount": payment_term_outstanding,
				}
			)

	return references


def get_paid_amount(dt, dn, party_type, party, account, due_date):
	if party_type == "Customer":
		dr_or_cr = "credit_in_account_currency - debit_in_account_currency"
	else:
		dr_or_cr = "debit_in_account_currency - credit_in_account_currency"

	paid_amount = frappe.db.sql(
		"""
		select ifnull(sum({dr_or_cr}), 0) as paid_amount
		from `tabGL Entry`
		where against_voucher_type = %s
			and against_voucher = %s
			and party_type = %s
			and party = %s
			and account = %s
			and due_date = %s
			and {dr_or_cr} > 0
	""".format(
			dr_or_cr=dr_or_cr
		),
		(dt, dn, party_type, party, account, due_date),
	)

	return paid_amount[0][0] if paid_amount else 0


@frappe.whitelist()
def get_party_and_account_balance(
	company, date, paid_from=None, paid_to=None, ptype=None, pty=None, cost_center=None
):
	return frappe._dict(
		{
			"party_balance": get_balance_on(party_type=ptype, party=pty, cost_center=cost_center),
			"paid_from_account_balance": get_balance_on(paid_from, date, cost_center=cost_center),
			"paid_to_account_balance": get_balance_on(paid_to, date=date, cost_center=cost_center),
		}
	)


@frappe.whitelist()
def make_payment_order(source_name, target_doc=None):
	from frappe.model.mapper import get_mapped_doc

	def set_missing_values(source, target):
		target.payment_order_type = "Payment Entry"
		target.append(
			"references",
			dict(
				reference_doctype="Payment Entry",
				reference_name=source.name,
				bank_account=source.party_bank_account,
				amount=source.paid_amount,
				account=source.paid_to,
				supplier=source.party,
				mode_of_payment=source.mode_of_payment,
			),
		)

	doclist = get_mapped_doc(
		"Payment Entry",
		source_name,
		{
			"Payment Entry": {
				"doctype": "Payment Order",
				"validation": {"docstatus": ["=", 1]},
			}
		},
		target_doc,
		set_missing_values,
	)

	return doclist

def get_bank_cash_account(doc, bank_account):
	bank = get_default_bank_cash_account(
		doc.company, "Bank", mode_of_payment=doc.get("mode_of_payment"), account=bank_account
	)

	if not bank:
		bank = get_default_bank_cash_account(
			doc.company, "Cash", mode_of_payment=doc.get("mode_of_payment"), account=bank_account
		)

	return bank


def create_payment_entry(self, submit=True):
    
    """create entry"""
    frappe.flags.ignore_account_permission = True

    ref_doc = frappe.get_doc(self.reference_doctype, self.reference_name)

    if self.reference_doctype in ["Sales Invoice", "POS Invoice"]:
        party_account = ref_doc.debit_to
    elif self.reference_doctype == "Purchase Invoice":
        party_account = ref_doc.credit_to
    else:
        party_account = get_party_account("Customer", ref_doc.get("customer"), ref_doc.company)

    party_account_currency = ref_doc.get("party_account_currency") or get_account_currency(
        party_account
    )

    bank_amount = self.grand_total
    if (
        party_account_currency == ref_doc.company_currency and party_account_currency != self.currency
    ):
        party_amount = ref_doc.base_grand_total
    else:
        party_amount = self.grand_total

    payment_entry = get_payment_entry(
        self.reference_doctype,
        self.reference_name,
        party_amount=party_amount,
        bank_account=self.payment_account,
        bank_amount=bank_amount,
    )

    payment_entry.update(
        {
            "reference_no": self.name,
            "reference_date": nowdate(),
            "remarks": "Payment Entry against {0} {1} via Payment Request {2}".format(
                self.reference_doctype, self.reference_name, self.name
            ),
        }
    )

    if payment_entry.difference_amount:
        company_details = get_company_defaults(ref_doc.company)

        payment_entry.append(
            "deductions",
            {
                "account": company_details.exchange_gain_loss_account,
                "cost_center": company_details.cost_center,
                "amount": payment_entry.difference_amount,
            },
        )

    if submit:
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()

    return payment_entry

def set_missing_values(self):
    if self.payment_type == "Internal Transfer":
        for field in (
            "party",
            "party_balance",
            "total_allocated_amount",
            "base_total_allocated_amount",
            "unallocated_amount",
        ):
            self.set(field, None)
        self.references = []
    else:
        if not self.party_type:
            frappe.throw(_("Party Type is mandatory"))

        if not self.party:
            frappe.throw(_("Party is mandatory"))

        _party_name = (
            "title" if self.party_type in ("Student", "Student Applicant","Shareholder") else self.party_type.lower() + "_name"
        )
        
        self.party_name = frappe.db.get_value(self.party_type, self.party, _party_name)
        
    if self.party:
        if not self.party_balance:
            self.party_balance = get_balance_on(
                party_type=self.party_type, party=self.party, date=self.posting_date, company=self.company
            )

        if not self.party_account:
            party_account = get_party_account(self.party_type, self.party, self.company)
            self.set(self.party_account_field, party_account)
            self.party_account = party_account

    if self.paid_from and not (self.paid_from_account_currency or self.paid_from_account_balance):
        acc = get_account_details(self.paid_from, self.posting_date, self.cost_center)
        self.paid_from_account_currency = acc.account_currency
        self.paid_from_account_balance = acc.account_balance

    if self.paid_to and not (self.paid_to_account_currency or self.paid_to_account_balance):
        acc = get_account_details(self.paid_to, self.posting_date, self.cost_center)
        self.paid_to_account_currency = acc.account_currency
        self.paid_to_account_balance = acc.account_balance

    self.party_account_currency = (
        self.paid_from_account_currency
        if self.payment_type == "Receive"
        else self.paid_to_account_currency
    )

    self.set_missing_ref_details()


def validate_reference_documents(self):
	
	if self.party_type == "Student":
		valid_reference_doctypes = "Fees"
	if self.party_type == "Student Applicant":
		valid_reference_doctypes = "Fees"
	elif self.party_type == "Customer":
		valid_reference_doctypes = ("Sales Order", "Sales Invoice", "Journal Entry", "Dunning")
	elif self.party_type == "Supplier":
		valid_reference_doctypes = ("Purchase Order", "Purchase Invoice", "Journal Entry")
	elif self.party_type == "Employee":
		valid_reference_doctypes = ("Expense Claim", "Journal Entry", "Employee Advance", "Gratuity")
	elif self.party_type == "Shareholder":
		valid_reference_doctypes = "Journal Entry"
	elif self.party_type == "Donor":
		valid_reference_doctypes = "Donation"

	for d in self.get("references"):
		if not d.allocated_amount:
			continue
		
		if d.reference_doctype not in valid_reference_doctypes:
			frappe.throw(
				_("Reference Doctype must be one of {0}").format(comma_or(valid_reference_doctypes))
			)

		elif d.reference_name:
			if not frappe.db.exists(d.reference_doctype, d.reference_name):
				frappe.throw(_("{0} {1} does not exist").format(d.reference_doctype, d.reference_name))
			else:
				ref_doc = frappe.get_doc(d.reference_doctype, d.reference_name)

				if d.reference_doctype != "Journal Entry":
					if self.party != ref_doc.get(scrub(self.party_type)):
						if self.party_type == 'Student Applicant':
							pass
						else:
							frappe.throw(
								_("{0} {1} is not associated with {2} {3}").format(
									d.reference_doctype, d.reference_name, self.party_type, self.party
								)
							)
				else:
					self.validate_journal_entry()

				if d.reference_doctype in ("Sales Invoice", "Purchase Invoice", "Expense Claim", "Fees"):
					if self.party_type == "Customer":
						ref_party_account = (
							get_party_account_based_on_invoice_discounting(d.reference_name) or ref_doc.debit_to
						)
					elif self.party_type == "Student" or "Student Applicant":
						ref_party_account = ref_doc.receivable_account
					elif self.party_type == "Supplier":
						ref_party_account = ref_doc.credit_to
					elif self.party_type == "Employee":
						ref_party_account = ref_doc.payable_account

					if ref_party_account != self.party_account:
						frappe.throw(
							_("{0} {1} is associated with {2}, but Party Account is {3}").format(
								d.reference_doctype, d.reference_name, ref_party_account, self.party_account
							)
						)

				if ref_doc.docstatus != 1:
					frappe.throw(_("{0} {1} must be submitted").format(d.reference_doctype, d.reference_name))



@frappe.whitelist()
def get_outstanding_reference_documents(args):

	if isinstance(args, string_types):
		args = json.loads(args)

	if args.get("party_type") == "Member":
		return

	# confirm that Supplier is not blocked
	if args.get("party_type") == "Supplier":
		supplier_status = get_supplier_block_status(args["party"])
		if supplier_status["on_hold"]:
			if supplier_status["hold_type"] == "All":
				return []
			elif supplier_status["hold_type"] == "Payments":
				if (
					not supplier_status["release_date"] or getdate(nowdate()) <= supplier_status["release_date"]
				):
					return []

	party_account_currency = get_account_currency(args.get("party_account"))
	company_currency = frappe.get_cached_value("Company", args.get("company"), "default_currency")

	# Get positive outstanding sales /purchase invoices/ Fees
	condition = ""
	if args.get("voucher_type") and args.get("voucher_no"):
		condition = " and voucher_type={0} and voucher_no={1}".format(
			frappe.db.escape(args["voucher_type"]), frappe.db.escape(args["voucher_no"])
		)

	# Add cost center condition
	if args.get("cost_center"):
		condition += " and cost_center='%s'" % args.get("cost_center")

	date_fields_dict = {
		"posting_date": ["from_posting_date", "to_posting_date"],
		"due_date": ["from_due_date", "to_due_date"],
	}

	for fieldname, date_fields in date_fields_dict.items():
		if args.get(date_fields[0]) and args.get(date_fields[1]):
			condition += " and {0} between '{1}' and '{2}'".format(
				fieldname, args.get(date_fields[0]), args.get(date_fields[1])
			)

	if args.get("company"):
		condition += " and company = {0}".format(frappe.db.escape(args.get("company")))

	outstanding_invoices = get_outstanding_invoices(
		args.get("party_type"),
		args.get("party"),
		args.get("party_account"),
		filters=args,
		condition=condition,
	)

	outstanding_invoices = split_invoices_based_on_payment_terms(outstanding_invoices)

	for d in outstanding_invoices:
		d["exchange_rate"] = 1
		if party_account_currency != company_currency:
			if d.voucher_type in ("Sales Invoice", "Purchase Invoice", "Expense Claim"):
				d["exchange_rate"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "conversion_rate")
			elif d.voucher_type == "Journal Entry":
				d["exchange_rate"] = get_exchange_rate(
					party_account_currency, company_currency, d.posting_date
				)
		if d.voucher_type in ("Purchase Invoice"):
			d["bill_no"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "bill_no")

	# Get all SO / PO which are not fully billed or against which full advance not paid
	orders_to_be_billed = []
	if args.get("party_type") != "Student" or "Student Applicant":
		orders_to_be_billed = get_orders_to_be_billed(
			args.get("posting_date"),
			args.get("party_type"),
			args.get("party"),
			args.get("company"),
			party_account_currency,
			company_currency,
			filters=args,
		)

	# Get negative outstanding sales /purchase invoices
	negative_outstanding_invoices = []
	if args.get("party_type") not in ["Student", "Employee","Student Applicant"] and not args.get("voucher_no"):
		negative_outstanding_invoices = get_negative_outstanding_invoices(
			args.get("party_type"),
			args.get("party"),
			args.get("party_account"),
			party_account_currency,
			company_currency,
			condition=condition,
		)

	data = negative_outstanding_invoices + outstanding_invoices + orders_to_be_billed

	if not data:
		frappe.msgprint(
			_(
				"No outstanding invoices found for the {0} {1} which qualify the filters you have specified."
			).format(_(args.get("party_type")).lower(), frappe.bold(args.get("party")))
		)

	return data


def get_orders_to_be_billed(
	posting_date,
	party_type,
	party,
	company,
	party_account_currency,
	company_currency,
	cost_center=None,
	filters=None,
):
	if party_type == "Customer":
		voucher_type = "Sales Order"
	elif party_type == "Supplier":
		voucher_type = "Purchase Order"
	elif party_type == "Employee":
		voucher_type = None

	# Add cost center condition
	if voucher_type:
		doc = frappe.get_doc({"doctype": voucher_type})
		condition = ""
		if doc and hasattr(doc, "cost_center"):
			condition = " and cost_center='%s'" % cost_center

	orders = []
	if voucher_type:
		if party_account_currency == company_currency:
			grand_total_field = "base_grand_total"
			rounded_total_field = "base_rounded_total"
		else:
			grand_total_field = "grand_total"
			rounded_total_field = "rounded_total"

		orders = frappe.db.sql(
			"""
			select
				name as voucher_no,
				if({rounded_total_field}, {rounded_total_field}, {grand_total_field}) as invoice_amount,
				(if({rounded_total_field}, {rounded_total_field}, {grand_total_field}) - advance_paid) as outstanding_amount,
				transaction_date as posting_date
			from
				`tab{voucher_type}`
			where
				{party_type} = %s
				and docstatus = 1
				and company = %s
				and ifnull(status, "") != "Closed"
				and if({rounded_total_field}, {rounded_total_field}, {grand_total_field}) > advance_paid
				and abs(100 - per_billed) > 0.01
				{condition}
			order by
				transaction_date, name
		""".format(
				**{
					"rounded_total_field": rounded_total_field,
					"grand_total_field": grand_total_field,
					"voucher_type": voucher_type,
					"party_type": scrub(party_type),
					"condition": condition,
				}
			),
			(party, company),
			as_dict=True,
		)

	order_list = []
	for d in orders:
		if not (
			flt(d.outstanding_amount) >= flt(filters.get("outstanding_amt_greater_than"))
			and flt(d.outstanding_amount) <= flt(filters.get("outstanding_amt_less_than"))
		):
			continue

		d["voucher_type"] = voucher_type
		# This assumes that the exchange rate required is the one in the SO
		d["exchange_rate"] = get_exchange_rate(party_account_currency, company_currency, posting_date)
		order_list.append(d)

	return order_list

def get_negative_outstanding_invoices(
	party_type,
	party,
	party_account,
	party_account_currency,
	company_currency,
	cost_center=None,
	condition=None,
):
	voucher_type = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
	supplier_condition = ""
	if voucher_type == "Purchase Invoice":
		supplier_condition = "and (release_date is null or release_date <= CURDATE())"
	if party_account_currency == company_currency:
		grand_total_field = "base_grand_total"
		rounded_total_field = "base_rounded_total"
	else:
		grand_total_field = "grand_total"
		rounded_total_field = "rounded_total"

	return frappe.db.sql(
		"""
		select
			"{voucher_type}" as voucher_type, name as voucher_no,
			if({rounded_total_field}, {rounded_total_field}, {grand_total_field}) as invoice_amount,
			outstanding_amount, posting_date,
			due_date, conversion_rate as exchange_rate
		from
			`tab{voucher_type}`
		where
			{party_type} = %s and {party_account} = %s and docstatus = 1 and
			outstanding_amount < 0
			{supplier_condition}
			{condition}
		order by
			posting_date, name
		""".format(
			**{
				"supplier_condition": supplier_condition,
				"condition": condition,
				"rounded_total_field": rounded_total_field,
				"grand_total_field": grand_total_field,
				"voucher_type": voucher_type,
				"party_type": scrub(party_type),
				"party_account": "debit_to" if party_type == "Customer" else "credit_to",
				"cost_center": cost_center,
			}
		),
		(party, party_account),
		as_dict=True,
	)

@frappe.whitelist()
def get_party_details(company, party_type, party, date, cost_center=None):
	bank_account = ""
	if not frappe.db.exists(party_type, party):
		frappe.throw(_("Invalid {0}: {1}").format(party_type, party))

	party_account = get_party_account(party_type, party, company)

	account_currency = get_account_currency(party_account)
	account_balance = get_balance_on(party_account, date, cost_center=cost_center)
	_party_name = (
		"title" if party_type in ("Student", "Shareholder","Student Applicant") else party_type.lower() + "_name"
	)
	party_name = frappe.db.get_value(party_type, party, _party_name)
	party_balance = get_balance_on(party_type=party_type, party=party, cost_center=cost_center)
	if party_type in ["Customer", "Supplier"]:
		bank_account = get_party_bank_account(party_type, party)

	return {
		"party_account": party_account,
		"party_name": party_name,
		"party_account_currency": account_currency,
		"party_balance": party_balance,
		"account_balance": account_balance,
		"bank_account": bank_account,
	}


# to be overriden
def get_outstanding_on_journal_entry(name):
	res = frappe.db.sql(
		"SELECT "
		'CASE WHEN party_type IN ("Customer", "Student","Student Applicant") '
		"THEN ifnull(sum(debit_in_account_currency - credit_in_account_currency), 0) "
		"ELSE ifnull(sum(credit_in_account_currency - debit_in_account_currency), 0) "
		"END as outstanding_amount "
		"FROM `tabGL Entry` WHERE (voucher_no=%s OR against_voucher=%s) "
		"AND party_type IS NOT NULL "
		'AND party_type != ""',
		(name, name),
		as_dict=1,
	)

	outstanding_amount = res[0].get("outstanding_amount", 0) if res else 0

	return outstanding_amount



def send_email(self):
	"""send email with payment link"""
	email_args = {
		"recipients": self.email_to,
		"sender": None,
		"subject": self.subject,
		"message": self.get_message(),
		"now": True,
		"attachments": [
			frappe.attach_print(
				self.reference_doctype,
				self.reference_name,
				file_name=self.reference_name,
				print_format=self.print_format,
			)
		],
	}
	enqueue(method=frappe.sendmail, queue="short", timeout=300, is_async=True, **email_args)


def get_payment_url(self):
	# check if payment url/integration request already exists
	integration_request = frappe.db.exists('Integration Request',{'reference_doctype':self.party_type,'reference_docname':self.party})
	if integration_request:
		integration_request_name = frappe.db.get_value('Integration Request',{'reference_doctype':self.party_type,'reference_docname':self.party},'name')
		payment_url = get_url("/paystack/pay?payment_id={0}".format(integration_request_name))
		return payment_url
	if self.reference_doctype != "Fees":
		data = frappe.db.get_value(
			self.reference_doctype, self.reference_name, ["company", "customer_name"], as_dict=1
		)
	else:
		data = frappe.db.get_value(
			self.reference_doctype, self.reference_name, ["student_name"], as_dict=1
		)
		data.update({"company": frappe.defaults.get_defaults().company})

	controller = get_payment_gateway_controller(self.payment_gateway)
	controller.validate_transaction_currency(self.currency)

	if hasattr(controller, "validate_minimum_transaction_amount"):
		controller.validate_minimum_transaction_amount(self.currency, self.grand_total)

	return controller.get_payment_url(
		**{
			"amount": flt(self.grand_total, self.precision("grand_total")),
			"title": data.company.encode("utf-8"),
			"description": self.subject.encode("utf-8"),
			"reference_doctype": "Payment Request",
			"reference_docname": self.name,
			"payer_email": self.email_to or frappe.session.user,
			"payer_name": frappe.safe_encode(data.customer_name),
			"order_id": self.name,
			"currency": self.currency,
		}
	)

