# Copyright (c) 2021, Anthony Emmanuel (Ghorz.com) and contributors
# For license information, please see license.txt


from __future__ import unicode_literals
import frappe
from frappe import _
import json
import hmac
import razorpay
import hashlib
from six.moves.urllib.parse import urlencode
from frappe.utils import flt
from frappe.model.document import Document
from frappe.utils import get_url, call_hook_method, cint, get_timestamp
from frappe.integrations.utils import (make_get_request, make_post_request, create_request_log,
	create_payment_gateway)


class PaystackSettings(Document):

	supported_currencies = ["NGN", "USD", "GHS", "ZAR"]

	def after_insert(self):
		create_payment_gateway(self.doctype)
		if not frappe.db.exists("Payment Gateway", self.name):
			payment_gateway = frappe.get_doc({
				"doctype": "Payment Gateway",
				"gateway": self.name,
				"gateway_settings": 'Paystack Settings',
				"gateway_controller": self.name
			})
			payment_gateway.insert(ignore_permissions=True)
			call_hook_method('payment_gateway_enabled', gateway=self.name)


	def validate(self):
		pass
		# create_payment_gateway(self.gateway_name)
		# call_hook_method('payment_gateway_enabled', gateway=self.gateway_name)

	def validate_transaction_currency(self, currency):
		if currency not in self.supported_currencies:
			frappe.throw(_("Please select another payment method. Paystack does not support transactions in currency '{0}'").format(currency))


	def get_payment_url(self, **kwargs):
		'''Return payment url with several params'''
		# create unique order id by making it equal to the integration request
		fees = get_paystack_fee(kwargs['amount'],doc=self)
		kwargs.update(fees)
		integration_request = create_request_log(kwargs, "Host", "Paystack")
		kwargs.update(dict(order_id=integration_request.name))
		# get fees
		
		integration_request.db_set('customer_email',kwargs.get('payer_email'))
		integration_request.db_set('customer_name',kwargs.get('payer_name'))
		integration_request.db_set('total_amount',kwargs.get('total_amount'))
		integration_request.db_set('customer_fee',kwargs.get('customer_fee'))
		integration_request.db_set('balance',kwargs.get('balance'))
		integration_request.db_set('paystack_fee',kwargs.get('paystack_fee'))



		frappe.db.commit()
		
		# add payment gateway name
		kwargs.update({'gateway':self.name})
		
		url =  get_url("/paystack/pay?payment_id={0}".format(integration_request.name))
		return url

	def calculate_paystack_fee(self,**kwargs):
		pass

def clean_data(data):
	try:
		split_first  = data.split(',')
		split_first[0] = split_first[0].replace('{', '')
		split_first[-1] = split_first[-1].replace('}', '')
		# make dict
		result = {}
		for i in split_first:
			i = i.replace(" '", '').replace("'", '')
			_d = i.split(':')
			# print("_d", _d)
			result[_d[0]] = _d[1]
	except Exception as e:
		result = str(e)
	return result

# webhook
@frappe.whitelist(allow_guest=True)
def webhook(request):
	print(request)


def get_paystack_fee(amount=0.0,doc=None):
	"""get paystack fee"""
	from frappe.utils import flt
	# Wallet fundings 1.5% + N100
	
	amount = flt(amount)
	fees_limit = flt(doc.get('fees_limit'))
	percentage = flt(doc.get('paystack_percentage'))
	fixed_fee_reference = flt(doc.get('fixed_fee_threshold'))
	
	fixed_fee = 0
	if amount > fixed_fee_reference:
		fixed_fee = flt(doc.get('paystack_fixed_fee'))

	paystack_fee = round_up(((percentage*amount/100)+fixed_fee)/(1-(percentage/100)), 2)
	
	if paystack_fee > fees_limit:		# fees are capped at this amount
		paystack_fee = fees_limit
	
	
	balance = flt((amount + paystack_fee) - amount)
	total_amount = amount + paystack_fee
	customer_fee = paystack_fee #customer fee will always be equal to fee for now, until custom or fractional fees are added as options
	
	fees = {
		'balance':balance,
		'paystack_fee':paystack_fee,
		'total_amount':total_amount,
		'customer_fee':customer_fee,
		'total_amount':total_amount
	}

	return fees

@frappe.whitelist()
def round_up(amount, precision=0):
	'''round up amount with the decimal part ceiled'''
	from math import ceil
	
	precision = float(10 ** cint(precision))
	return ceil(amount * precision)/precision