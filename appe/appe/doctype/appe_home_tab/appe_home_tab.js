// Copyright (c) 2026, Appe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Appe Home Tab", {
	refresh(frm) {

	},
});


frappe.ui.form.on("Appe Home Tab Items", {
	type(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        row.linked_doctype = "";

        if (row.type === "Report") {
            frappe.model.set_value(cdt, cdn, "linked_doctype", "Appe Report");
            frm.fields_dict.items.grid.grid_rows_by_docname[cdn].toggle_editable("linked_doctype", false);
        }

        else if (row.type === "Dashboard") {
            frappe.model.set_value(cdt, cdn, "linked_doctype", "Dashboard");
            frm.fields_dict.items.grid.grid_rows_by_docname[cdn].toggle_editable("linked_doctype", false);
        }

        else if (row.type === "Workspace") {
            frappe.model.set_value(cdt, cdn, "linked_doctype", "Workspace");
            frm.fields_dict.items.grid.grid_rows_by_docname[cdn].toggle_editable("linked_doctype", false);
        }

        else if (row.type === "Screen") {
            frappe.model.set_value(cdt, cdn, "linked_doctype", "Appe Screen");
            frm.fields_dict.items.grid.grid_rows_by_docname[cdn].toggle_editable("linked_doctype", false);
        }

        else {
            frappe.model.set_value(cdt, cdn, "linked_doctype", "");
        }

        frm.refresh_field("items");
    },

    refrence_docname(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.type === "Screen" && row.refrence_docname) {
            frappe.db.get_value(
                "Appe Screen",
                row.refrence_docname,
                "route",
                function(r) {
                    console.log(r)
                    if (r && r.route) {
                        frappe.model.set_value(cdt, cdn, "appe_screen", r.route);
                    }
                }
            );
        }
        frm.refresh_field("items");

    }
});
