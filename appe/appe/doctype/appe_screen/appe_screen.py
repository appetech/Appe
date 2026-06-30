# Copyright (c) 2025, Kamesh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from appe.setup.default_appe_screens import create_default_appe_screens


class AppeScreen(Document):
	pass


@frappe.whitelist()
def fetch_default_screens():
	if not frappe.has_permission("Appe Screen", "create"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	result = create_default_appe_screens()
	frappe.db.commit()
	return result
