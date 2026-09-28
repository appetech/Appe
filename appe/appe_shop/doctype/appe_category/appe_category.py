# Copyright (c) 2026, Appe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.nestedset import NestedSet


class AppeCategory(NestedSet):
	def validate(self):
		if not self.title:
			self.title = self.category
		
