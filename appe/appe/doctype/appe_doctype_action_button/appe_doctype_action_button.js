// Copyright (c) 2026, Appe technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Appe Doctype Action Button", {
	refresh(frm) {
        frm.set_query('print_format', function() {
            return {
                filters: {
                    'doc_type': frm.doc.reference_doctype
                }
            };
        });

	},

    print_format: function(frm) {
        frm.set_query('print_format', function() {
            return {
                filters: {
                    'doc_type': frm.doc.reference_doctype
                }
            };
        });

    }
});
