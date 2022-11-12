# -*- coding: utf-8 -*-
from __future__ import unicode_literals

__version__ = '0.0.4'
# import frappe
# from frappe.website.doctype.web_form import web_form
# def get_fees_class():
#     from erpnext.education.doctype.fees import fees
#     return fees
# from paystack_school.overrides import (create_payment_entry, make_gl_entries,on_submit,
#     get_payment_gateway_url,get_payment_entry, set_missing_values,get_payment_url,
#     validate_reference_documents,get_outstanding_on_journal_entry,get_party_details)
# from erpnext.accounts.doctype.payment_entry import payment_entry
# from erpnext.accounts.doctype.payment_request import payment_request




# # override get_payment_url_function
# web_form.WebForm.get_payment_gateway_url = get_payment_gateway_url
# fees = get_fees_class()
# fees.Fees.make_gl_entries = make_gl_entries
# fees.Fees.on_submit = on_submit

# # payment_entry.get_payment_entry = get_payment_entry
# payment_request.PaymentRequest.create_payment_entry = create_payment_entry
# payment_request.PaymentRequest.get_payment_url = get_payment_url
# payment_entry.PaymentEntry.set_missing_values = set_missing_values
# payment_entry.PaymentEntry.validate_reference_documents = validate_reference_documents
# payment_entry.get_outstanding_on_journal_entry = get_outstanding_on_journal_entry
# payment_entry.get_party_details = get_party_details
