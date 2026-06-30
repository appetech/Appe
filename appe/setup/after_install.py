import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from appe.setup.default_appe_screens import create_default_appe_screens
from appe.setup.default_mobile_app_module import create_default_mobile_app_module


def after_install():
	create_default_appe_screens()
	create_default_mobile_app_module()

	if frappe.db.exists("DocType", "Employee"):
		create_employee_fields()

def create_employee_fields():
    custom_fields = {
        "Employee": [
            {
                "fieldname": "appe_setting_tab",
                "fieldtype": "Tab Break",
                "label": "Appe Setting",
                "insert_after": "feedback",
                "module": "Appe"
            },
            {
                "fieldname": "checkin_mandatory",
                "fieldtype": "Check",
                "label": "Check-in Mandatory",
                "default": "0",
                "insert_after": "appe_setting_tab",
                "module": "Appe"
            },
            {
                "fieldname": "enable_live_location_tracking",
                "fieldtype": "Check",
                "label": "Enable Live Location Tracking",
                "default": "0",
                "insert_after": "checkin_mandatory",
                "module": "Appe"
            },
            {
                "fieldname": "appe_status",
                "fieldtype": "Select",
                "label": "Status",
                "options": "Active\nDisabled",
                "insert_after": "checkin_mandatory",
                "module": "Appe"
            }
        ]
    }

    create_custom_fields(custom_fields)

def after_uninstall():
    if frappe.db.exists("DocType", "Employee"):
        remove_employee_fields()
        remove_property_setters()
        remove_custom_fields()
        frappe.db.commit()

def remove_employee_fields():
    custom_fields = [
        "checkin_mandatory",
        "enable_live_location_tracking",
        "appe_status",
        "appe_setting_tab"
    ]

    for field in custom_fields:
        if frappe.db.exists("Custom Field", {"fieldname": field, "dt": "Employee"}):
            frappe.delete_doc("Custom Field", {"fieldname": field, "dt": "Employee"})

def remove_property_setters():
    """Remove any Property Setters created by this app."""
    try:
        appe_doctypes = [
            "Employee",      # Add/remove based on what your app modifies
        ]
        for doctype in appe_doctypes:
            records = frappe.get_all(
                "Property Setter",
                filters={"doc_type": doctype, "module": "Appe"},
            )
            for r in records:
                frappe.delete_doc(
                    "Property Setter", r.name,
                    ignore_permissions=True,
                    force=True
                )
    except Exception as e:
        frappe.log_error(f"Appe uninstall: error removing Property Setters: {e}")


def remove_custom_fields():
    try:
        records = frappe.get_all(
            "Custom Field",
            filters={"module": "Appe"}
        )
        for r in records:
            frappe.delete_doc(
                "Custom Field", r.name,
                ignore_permissions=True,
                force=True
            )
    except Exception as e:
        frappe.log_error(f"Appe uninstall: error removing Custom Fields: {e}")