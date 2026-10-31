// Copyright (c) 2026, Appe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Appe Category", {
	category(frm) {
		if (!frm.doc.title && frm.doc.category) {
			frm.set_value("title", frm.doc.category);
		}
	},
});
