
import frappe
import hmac
import json
import math
import hashlib
import requests
from urllib.parse import urlparse, parse_qs
from paystack_school.api.v1 import verify_transaction


@frappe.whitelist(allow_guest=True)
def handle_webhook_response(*args,**kwargs):
	try:
		frappe.log_error(json.dumps(kwargs,indent=4),'kwargs')
		if kwargs:
			webhook_response = frappe._dict(kwargs)
			webhook_data = json.loads(webhook_response.data)

		signature = frappe.get_request_header('x-paystack-signature')
		if verify_paystack_signature_and_ip(signature=signature,data=webhook_data):
			
			metadata = (((webhook_data.get('data') or {}).get('metadata')) or {})
			metadata_url = metadata.get('referrer')
			metadata_url = urlparse(metadata_url)
			query = parse_qs(metadata_url.query)
			ret_query = dict()
			for i in query:
				ret_query.update({i: query[i][0]})

			if verify_recipient_site(metadata_url):
				#check if payment has been processed on the system
				#get integration request
				if frappe.db.exists('Integration Request',ret_query.get('payment_id')):
					status = frappe.db.get_value('Integration Request',ret_query.get('payment_id'),'status')
					if status != 'Authorized' or 'Completed':
						#attempt to verify and update the integration request
						metadata_url = (((webhook_data.get('data') or {}).get('metadata'))
						 or {}).get('payment_request','')

						payload = {
							'payment_request_name':metadata.get('payment_request_name'),
							'gateway':metadata.get('gateway'),
							'reference':metadata.get('payment_reference'),
							'payment_id':ret_query.get('payment_id')
						}
						if verify_transaction(payload):
							frappe.local.response['http_status_code'] = 200
							frappe.local.response['message'] = 'Webhook Received Successfully'

	except:
		frappe.local.response['http_status_code'] = 400
		frappe.local.response['message'] = 'Internal Server Error'
		frappe.log_error(frappe.get_traceback(),'webhook_response_failure')

def verify_paystack_signature_and_ip(signature='',data={}):

	if not signature:
		return False

	check_ip = False
	check_signature = False
	request_ip = frappe.local.request_ip
	gateway = data['metadata']['gateway']
	if gateway:
		whitelisted_ips = [i.ip for i in frappe.get_doc('Paystack Settings',gateway).ip_address]
	if request_ip in whitelisted_ips:
		check_ip = True

	#check paystack signature

	controller = frappe.get_doc('Paystack Settings',gateway)
	secret_key = controller.get_password(fieldname='live_secret_key',raise_exception=False)

	hashkey = frappe.utils.cstr(secret_key).encode()
	hashobj = frappe.utils.cstr(data).encode()
	msg_hash = hmac.new(hashkey, hashobj, hashlib.sha512).hexdigest()
	if msg_hash == signature:
		check_signature = True  

	if check_signature and check_ip:
		return True
	else:
		frappe.throw('verify_paystack_signature_failed')

    


def verify_recipient_site(metadata_url):

	
	verify_site = False
	
	site_url = urlparse(frappe.utils.get_url())
	if not metadata_url.netloc or site_url.netloc == metadata_url.netloc:
		verify_site = True
		return verify_site
	else:
		frappe.throw(json.dumps({'site_url':site_url.netloc,'metadata_url':metadata_url.netloc}),'verify_recipient_site_failed')


"""
{  
  "event":"charge.success",
  "data": {  
    "id":302961,
    "domain":"live",
    "status":"success",
    "reference":"qTPrJoy9Bx",
    "amount":10000,
    "message":null,
    "gateway_response":"Approved by Financial Institution",
    "paid_at":"2016-09-30T21:10:19.000Z",
    "created_at":"2016-09-30T21:09:56.000Z",
    "channel":"card",
    "currency":"NGN",
    "ip_address":"41.242.49.37",
    "metadata":0,
    "log":{  
      "time_spent":16,
      "attempts":1,
      "authentication":"pin",
      "errors":0,
      "success":false,
      "mobile":false,
      "input":[],
      "channel":null,
      "history":[  
        {  
          "type":"input",
          "message":"Filled these fields: card number, card expiry, card cvv",
          "time":15
        },
        {  
          "type":"action",
          "message":"Attempted to pay",
          "time":15
        },
        {  
          "type":"auth",
          "message":"Authentication Required: pin",
          "time":16
        }
      ]
    },
    "fees":null,
    "customer":{  
      "id":68324,
      "first_name":"BoJack",
      "last_name":"Horseman",
      "email":"bojack@horseman.com",
      "customer_code":"CUS_qo38as2hpsgk2r0",
      "phone":null,
      "metadata":null,
      "risk_action":"default"
    },
    "authorization":{  
      "authorization_code":"AUTH_f5rnfq9p",
      "bin":"539999",
      "last4":"8877",
      "exp_month":"08",
      "exp_year":"2020",
      "card_type":"mastercard DEBIT",
      "bank":"Guaranty Trust Bank",
      "country_code":"NG",
      "brand":"mastercard",
      "account_name": "BoJack Horseman"
    },
    "plan":{}
  } 
}
"""