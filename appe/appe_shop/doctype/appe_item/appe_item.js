// Copyright (c) 2026, Appe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Appe Item", {
	refresh(frm) {
		frm.trigger("set_discount");
	},
	item_name(frm) {
		if (!frm.doc.item_code && frm.doc.item_name) {
			frm.set_value(
				"item_code",
				frm.doc.item_name
					.trim()
					.replace(/\s+/g, "-")
					.replace(/[^A-Za-z0-9\-]/g, "")
					.toUpperCase()
			);
		}
	},
	mrp(frm) {
		frm.trigger("set_discount");
	},
	rate(frm) {
		frm.trigger("set_discount");
	},
	uom_doctype(frm) {
		frm.set_value("uom", "");
	},
	set_discount(frm) {
		const mrp = flt(frm.doc.mrp);
		const rate = flt(frm.doc.rate);
		let discount = 0;
		if (mrp && rate && mrp >= rate) {
			discount = ((mrp - rate) / mrp) * 100;
		}
		frm.set_value("discount_percentage", discount);
	},
});
