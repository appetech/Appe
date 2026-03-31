import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    create_employee_fields()

def create_employee_fields():
    custom_fields = {
        "Employee": [
            {
                "fieldname": "appe_setting_tab",
                "fieldtype": "Tab Break",
                "label": "Appe Setting",
                "insert_after": "feedback"
            },
            {
                "fieldname": "checkin_mandatory",
                "fieldtype": "Check",
                "label": "Check-in Mandatory",
                "default": "0",
                "insert_after": "appe_setting_tab"
            },
            {
                "fieldname": "enable_live_location_tracking",
                "fieldtype": "Check",
                "label": "Enable Live Location Tracking",
                "default": "0",
                "insert_after": "checkin_mandatory"
            },
            {
                "fieldname": "appe_status",
                "fieldtype": "Select",
                "label": "Status",
                "options": "Active\nDisabled",
                "insert_after": "checkin_mandatory"
            }
        ]
    }

    create_custom_fields(custom_fields)