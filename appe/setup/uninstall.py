import frappe

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
        "appe_setting_tab",
        "checkin_blocks_other_features"
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