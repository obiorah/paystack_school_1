import frappe


def after_install():
    modify_fees_and_program_doctype()

def modify_fees_and_program_doctype():
    student = frappe.get_meta('Fees').get_field('student')
    program = frappe.get_meta('Fees').get_field('program')
    
    student.db_set('reqd',0)
    student.db_set('fieldtype','Dynamic Link')
    student.db_set('options','fee_document_type')
    
    program.db_set('reqd',0)
    frappe.db.commit()


def add_party_type():
    doc = frappe.new_doc('Party Type')
    doc.party_type = "Student Applicant"
    doc.account_type = "Receivable"
    doc.save()