from . import __version__ as app_version

app_name = "paystack_school"
app_title = "Paystack School"
app_publisher = "Odera"
app_description = "Paystack for Schools"
app_icon = "octicon octicon-file-directory"
app_color = "blue"
app_email = "okonkwooderao@gmail.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/paystack_school/css/paystack_school.css"
# app_include_js = "/assets/paystack_school/js/paystack_school.js"

# include js, css files in header of web template
# web_include_css = "/assets/paystack_school/css/paystack_school.css"
# web_include_js = "/assets/paystack_school/js/paystack_school.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "paystack_school/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "paystack_school.install.before_install"
after_install = "paystack_school.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "paystack_school.uninstall.before_uninstall"
# after_uninstall = "paystack_school.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "paystack_school.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Web Form":"paystack_school.overrides.CustomWebForm",
	"Payment Request":"paystack_school.overrides.CustomPaymentRequest",
	"Payment Entry":"paystack_school.overrides.CustomPaymentEntry",
	"Fees":"paystack_school.overrides.CustomFees"
}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"paystack_school.tasks.all"
# 	],
# 	"daily": [
# 		"paystack_school.tasks.daily"
# 	],
# 	"hourly": [
# 		"paystack_school.tasks.hourly"
# 	],
# 	"weekly": [
# 		"paystack_school.tasks.weekly"
# 	]
# 	"monthly": [
# 		"paystack_school.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "paystack_school.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"erpnext.accounts.doctype.payment_entry.payment_entry.get_outstanding_on_journal_entry":"paystack_school.overrides.get_outstanding_on_journal_entry"
	"erpnext.accounts.doctype.payment_entry.payment_entry.get_party_details = paystack_school.overrides.get_party_details"
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "paystack_school.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"paystack_school.auth.validate"
# ]

# Translation
# --------------------------------

# Make link fields search translated document names for these DocTypes
# Recommended only for DocTypes which have limited documents with untranslated names
# For example: Role, Gender, etc.
# translated_search_doctypes = []
