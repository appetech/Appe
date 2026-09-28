# Copyright (c) 2026, Appe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class AppeItem(Document):
	def before_naming(self):
		self.set_item_code()

	def validate(self):
		self.set_item_code()
		self.ensure_uom_doctype()
		self.set_discount()
		self.sync_primary_image()

	def set_item_code(self):
		if self.item_code or not self.item_name:
			return
		self.item_code = frappe.scrub(self.item_name).replace("_", "-").upper()

	def ensure_uom_doctype(self):
		if self.uom_doctype == "UOM" and not frappe.db.exists("DocType", "UOM"):
			self.uom_doctype = "Appe UOM"
		if not self.uom_doctype:
			self.uom_doctype = "Appe UOM"

	def set_discount(self):
		mrp = flt(self.mrp)
		rate = flt(self.rate)
		if rate and mrp and rate > mrp:
			frappe.throw("Selling Rate cannot be greater than MRP")
		if mrp and rate and mrp >= rate:
			self.discount_percentage = ((mrp - rate) / mrp) * 100
		else:
			self.discount_percentage = 0

	def sync_primary_image(self):
		primary = None
		for row in self.get("images") or []:
			if not row.image:
				continue
			if row.is_primary or not primary:
				primary = row.image
			if row.is_primary:
				break
		if primary and not self.image:
			self.image = primary
		if self.image and self.get("images"):
			matched = False
			for row in self.images:
				row.is_primary = 1 if row.image == self.image and not matched else 0
				if row.image == self.image:
					matched = True
			if not matched:
				self.append("images", {"image": self.image, "is_primary": 1})
