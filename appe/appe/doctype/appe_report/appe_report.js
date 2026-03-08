// Copyright (c) 2025, Kamesh and contributors
// For license information, please see license.txt
frappe.ui.form.on("Appe Report", {
    refresh(frm) {
        let field = frm.fields_dict.third_party_report_name;

        field.$input.on(
            "input",
            frappe.utils.debounce(function () {

                let text = $(this).val();
                console.log('text',text)

                frappe.call({
                    method: "appe.appe.doctype.appe_report.appe_report.get_third_party_reports",
                    args: {
                        appe_api_integration: frm.doc.appe_api_integration,
                        text: text
                    },
                    callback: function (r) {

                        if (r.message && field.set_data) {
                            field.set_data(r.message);   // 👈 important
                        }

                    }
                });

            }, 400)
        );

        // let field = frm.fields_dict.third_party_report_name.$input;

        // field.on("input", frappe.utils.debounce(function () {

        //     let text = $(this).val();

        //     if (!text) return;

        //     frappe.call({
        //         method: "appe.appe.doctype.appe_report.appe_report.get_third_party_reports",
        //         args: {
        //             appe_api_integration: frm.doc.appe_api_integration,
        //             text: text
        //         },
        //         callback: function (r) {
        //             console.log(r)

        //             if (r.message) {

        //                 frm.set_df_property(
        //                     "third_party_report_name",
        //                     "options",
        //                     r.message.join("\n")
        //                 );

        //             }

        //         }
        //     });

        // }, 500));
    }
});