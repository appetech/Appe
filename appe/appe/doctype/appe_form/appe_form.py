# Copyright (c) 2026, Appe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AppeForm(Document):
	pass


@frappe.whitelist()
def get_doctype_data(doctype_name):
	"""
	Reference Doctype ka complete data fetch karo — all fields (scalar + child tables).
	Returns a dict with all DocType meta information.
	"""
	if not doctype_name:
		frappe.throw(frappe._("Doctype name required"))

	# Permission check — sirf wahi DocType fetch ho jo user dekh sakta hai
	frappe.has_permission("DocType", throw=True)

	doc = frappe.get_doc("DocType", doctype_name)

	# Pura document dict me convert karo (child tables bhi include hote hain)
	data = doc.as_dict()

	# Internal Frappe meta keys hata do jo form me set karne ki zaroorat nahi
	keys_to_remove = [
		"name", "owner", "creation", "modified", "modified_by",
		"docstatus", "idx", "migration_hash", "__islocal", "__unsaved",
	]
	for key in keys_to_remove:
		data.pop(key, None)

	# Child table rows ke internal keys bhi saaf karo
	child_tables = ["fields", "permissions", "actions", "links", "states"]
	child_keys_to_remove = ["name", "owner", "creation", "modified", "modified_by",
							"docstatus", "parent", "parentfield", "parenttype", "idx"]

	for table in child_tables:
		if table in data and isinstance(data[table], list):
			cleaned_rows = []
			for row in data[table]:
				cleaned = {k: v for k, v in row.items() if k not in child_keys_to_remove}
				cleaned_rows.append(cleaned)
			data[table] = cleaned_rows

	return data
