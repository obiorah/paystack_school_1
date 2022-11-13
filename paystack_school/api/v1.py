import string
import frappe, requests, json, hmac, math, hashlib
from ldap3 import STRING_TYPES
from paystack_school.utils import (
    compute_received_hash, getip, is_paystack_ip,
    generate_digest,
)
from frappe import _
from math import ceil

@frappe.whitelist(allow_guest=True)
def get_payment_request(**kwargs):
    # get or create payment request data
    try:
        frappe.log_error(kwargs,'get_payment_request')
        data = frappe.form_dict
        payment_request = None
        fees = None
        payment_request = None

        if data.reference_doctype != "Payment Request":

            if not frappe.db.exists('Fees',{'reference_doctype':data.reference_doctype,'reference_docname':data.reference_docname}):
                # create fees
                fees = create_fees(data)
                fees.submit()
            else:
                fees = frappe.get_doc('Fees',{'reference_doctype':data.reference_doctype,'reference_docname':data.reference_docname})
            if not frappe.db.exists('Payment Request',{'party_type':data.reference_doctype,'party':data.reference_docname}):
                # create a payment request
                if data.reference_doctype == 'Student Applicant':
                    party_type = 'Student Applicant'
                else:
                    party_type = data.reference_doctype

                # get payment_request email message
                message = frappe.db.get_value('Accounts Table',{'document':data.reference_doctype},'message_template')
                payment_request = frappe.get_doc({
                    'doctype':'Payment Request',
                    'party_type':'Student Applicant',
                    'party': data.reference_docname,
                    'reference_doctype':'Fees',
                    'reference_name': fees.name,
                    'grand_total':data.amount,
                    'email_to':data.payer_email,
                    'payment_request_type':'Inward',
                    'payment_gateway_account': 'Paystack - NGN', #use this as default until there is a setting for it
                    'subject':"Student Application " + data.reference_docname,
                    'currency':'NGN',
                    'message':message
                })
                # update integration request reference doctype and reference docname
                
                payment_request.submit()

                frappe.db.commit()
            else:
                payment_request = frappe.get_doc('Payment Request',{'party_type':data.reference_doctype, 'party':data.reference_docname})
        else:
            # reference doctype is a payment request,
            payment_request = frappe.get_doc('Payment Request',data.reference_docname)   
        if not payment_request:return
        
        if(payment_request.payment_request_type=='Inward'):
            payment_keys = frappe.get_doc("Paystack Settings", payment_request.payment_gateway)
            return dict(
                key= payment_keys.live_public_key,
    		    email= data.payer_email,
    		    amount= ceil(float(kwargs.get('total_amount')) * 100),
    		    ref= payment_request.name,
    		    currency= payment_request.currency,
                status=payment_request.status,
    		    metadata={
    				'doctype': payment_request.doctype,
    				'docname': payment_request.name,
                    'reference_doctype': payment_request.reference_doctype,
                    'reference_name': payment_request.reference_name,
    				'gateway': payment_request.payment_gateway,
                    'payment_reference':generate_reference(),
                    'payment_request_name':payment_request.name
    	    	}
            )
        else:
            frappe.throw('Only Inward payment allowed.')
    except Exception as e:
        frappe.clear_last_message()
        frappe.clear_messages()
        frappe.log_error(frappe.get_traceback(),'get_payment_request')
        frappe.throw('Payment Error Please try again later')



@frappe.whitelist(allow_guest=True)
def webhook(**kwargs):
    form_dict = frappe.form_dict
    from_ip = frappe.local.request_ip
    v = verify_transaction(dict(
        gateway=frappe.form_dict.data['metadata']['gateway'],
        reference=frappe.form_dict.data['reference']
    ))

@frappe.whitelist(allow_guest=True)
def verify_transaction(payload):
    try:
        if isinstance(payload,STRING_TYPES):
            payload = json.loads(payload)
        gateway = frappe.get_doc("Paystack Settings", payload.get('gateway'))
        headers = {'Authorization': f"Bearer {gateway.get_password(fieldname='live_secret_key', raise_exception=False)}"}
        url = f"https://api.paystack.co/transaction/verify/{payload.get('reference')}"
        res = requests.get(url, headers=headers, timeout=60)
        resjson = res.json()
        if(res.status_code == 200):
            status = resjson.get('data').get('status')
            amount = resjson.get('data').get('amount')
            reference = resjson.get('data').get('reference')
            payment_request = frappe.get_doc('Payment Request', payload.get('payment_request_name'))
            resjson['data']['payment_request_name'] = payload.get('payment_request_name')
            if(status == 'success'):
                # make payment
                integration_request_query = frappe.db.exists('Integration Request',payload.get('payment_id'))
                if(integration_request_query):
                    integration_request = frappe.get_doc("Integration Request", integration_request_query)
                    payment_request.run_method("on_payment_authorized", 'Completed')
                    integration_request.db_set('status', 'Authorized')
                    #update integration reference_doc
                    update_integration_request_reference_doc(integration_request)
                    integration_request.db_set('error',json.dumps(resjson,indent=4))
                    # create log
                    create_log(resjson)

                    return True
                        # integration_request.db_set('status', 'Failed')
                else:
                    return False
            else:
                frappe.log_error(json.dumps(resjson.get('data')),'Payment Verification Failed')
                return
        else:
            frappe.log_erorr(res.text,'verification failure')
            return False
    #
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'Paystack Payment Verification Failure')
        return False

def create_log(resjson):
    try:
        data = resjson['data']
        payload = {
            'doctype': 'Paystack Payment Request',
            'reference' : data.get('reference'),
            'transaction_id' : data.get('id'),
            'amount' : data.get('amount'),
            'event' : data.get('status'),
            'order_id': data.get('payment_request_name'),
            'paid_at' : data.get('paid_at'),
            'created_at' : data.get('created_at'),
            'currency' : data.get('currency'),
            'paystack_fees':frappe.utils.flt(data.get('fees'))/100,
            'channel' : data.get('channel'),
            'reference_doctype' : data.get('metadata').get('reference_doctype'),
            'reference_docname' : data.get('metadata').get('reference_name'),
            'gateway' : data.get('metadata').get('gateway'),
            'customer_email' : data.get('customer').get('email'),
            'signature': data.get('authorization').get('signature'),
            'data': json.dumps(data,indent=4),
        }
        doc = frappe.get_doc(payload)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.respond_as_web_page('Payment Response','Payment Successful','success',http_status_code=200)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'Paystack log')

@frappe.whitelist(allow_guest=True)
def get_payment_data(payment_id):
    if frappe.db.exists('Integration Request',payment_id):
        status = frappe.db.get_value('Integration Request',payment_id,'status')
        if status in ['Authorized' or "Completed"]:
            # frappe.respond_as_web_page('Payment Response',html='Payment Already Processed/Payment Invalid')
            frappe.throw(_('Payment Already Processed/Payment Invalid'))
            # frappe.respond_as_web_page(_("Payment Response"),
			# _("Payment Already Processed/Payment Invalid"),
			#   indicator_color='red')
        data = frappe.db.get_value('Integration Request',payment_id,'data')
        data = json.loads(data)
        if not data.get('payer_name'):
            # get name from reference doc
            try:
                integration_reference_doc = frappe.get_doc(data.get('reference_doctype'),data.get('reference_docname'))
                reference_doc = frappe.get_doc(integration_reference_doc.party_type,integration_reference_doc.party)
                payer_name = reference_doc.get('title')
                if not payer_name:
                    payer_name = reference_doc.get('customer_name') #orders from shopping cart
                data['payer_name'] = payer_name
            except:
                frappe.log_error(frappe.get_traceback(),'traceback')
                data['payer_name'] = ''
        return data


def generate_reference(length=20):
    import random,string
    f_string =  ''.join(random.choices(string.ascii_uppercase + string.digits+string.ascii_lowercase, k = 20))
    return f_string


def create_fees(data={}):
    """create fees to be used as reference in payment request"""
    if not data:return
    data = frappe._dict(data)
    # get additional information and update data dict
    # this is assuming the ref doc is student applicant
    try:
        # if doctype is student applicant
        company = frappe.db.get_value(data.reference_doctype,data.reference_docname,'company')
    except:
        # if doctype is student
        company = frappe.db.get_value(data.reference_doctype,data.reference_docname,'school')
        
    data.company = company
    
    # get account info
    info = frappe.get_all('Accounts Table',filters={'document':data.reference_doctype},fields=['fee_structure','income_account','expense_account'])[0]

    data.fee_structure = info.get('fee_structure')
 
    # get fee structure components
    data.components = frappe.get_doc('Fee Structure',data.fee_structure).components

    data.income_account = info.get('income_account')
    data.expense_account = info.get('expense_account')
    data.cost_center = frappe.db.get_value('Company',data.company,'cost_center')
    

    fees = frappe.get_doc({
            'doctype':'Fees',
            'student_name':data.payer_name,
            'fee_document_type':data.reference_doctype,#this is a dynamic link
            'student':data.reference_docname,
            'due_date':frappe.utils.getdate(),
            'time':frappe.utils.now(),
            'institution':data.company,
            'reference_doctype':data.reference_doctype,
            'reference_docname':data.reference_docname,
            'student_email':data.payer_email,
            'fee_structure':data.fee_structure,
            'receivable_account':data.receivable_account,
            'income_account':data.income_account,
            'cost_center':data.cost_center,
            'components':data.components,
            'ignore_permissions':True
        })

    fees.flags.ignore_permissions = True
    frappe.session.user = 'Administrator'
    fees.save(ignore_permissions=True)
    fees.flags.ignore_permissions = False


    return fees


def update_integration_request_reference_doc(integration_request):
    """update the linked reference document
        linked document currently can only be one of [Student Applicant,Student',Sales Order(for payment made via store)]
    """

    try:
        reference_doc = frappe.get_doc(integration_request.reference_doctype,integration_request.reference_docname)
        if integration_request.status == 'Authorized' and integration_request.reference_doctype == 'Student Applicant':
            if reference_doc.application_status == 'Admitted':return
            reference_doc.paid = 1
            
            reference_doc.flags.ignore_mandatory = True
            reference_doc.flags.ignore_permissions = True
            reference_doc.save()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(),'update_integration')
        
            
        