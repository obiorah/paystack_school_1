import frappe


def after_install():
    modify_fees_and_program_doctype()
    add_party_type()
    add_role_permissions_to_student()

def modify_fees_and_program_doctype():
    student = frappe.get_meta('Fees').get_field('student')
    program = frappe.get_meta('Fees').get_field('program')
    student_admission = frappe.get_meta('Student Applicant').get_field('student_admission')
    
    student.db_set('reqd',0)
    student.db_set('fieldtype','Dynamic Link')
    student.db_set('options','fee_document_type')
    
    program.db_set('reqd',0)

    student_admission.db_set('reqd',0)
    frappe.db.commit()


def add_party_type():
    doc = frappe.new_doc('Party Type')
    if frappe.db.exists('Party Type','Student Applicant'):return
    doc.party_type = "Student Applicant"
    doc.account_type = "Receivable"
    doc.save()


def add_role_permissions_to_student():
    
    if frappe.db.exists('Role','Student'):
        doctypes = ['Payment Entry','Payment Request','Sales Order','Customer']

        #create custom docperms for the doctypes
        
        for doctype in doctypes:
            if frappe.db.exists('Custom DocPerm',{'parent':doctype,'role':'Student'}):
                continue
            perm = frappe.get_doc({
                'doctype':'Custom DocPerm',
                'write':1,
                'read':1,
                'create':1,
                'parent':doctype,
                'role':'Student'

            }).insert(ignore_permissions=True)

