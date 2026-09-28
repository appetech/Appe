// Copyright (c) 2026, Appe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Appe Form", {
    refresh(frm) {
        // ─── Get Doctype Data Button ───────────────────────────────────────
        frm.add_custom_button(__("Get Doctype Data"), function () {
            const refrence_doctype = frm.doc.refrence_doctype;

            if (!refrence_doctype) {
                frappe.msgprint({
                    title: __("Reference Doctype Required"),
                    message: __("Pehle 'Refrence Doctype' field me koi DocType select karo."),
                    indicator: "orange",
                });
                return;
            }

            frappe.call({
                method: "appe.appe.doctype.appe_form.appe_form.get_doctype_data",
                args: { doctype_name: refrence_doctype },
                freeze: true,
                freeze_message: __("Doctype data fetch ho raha hai..."),
                callback: function (r) {
                    if (r.exc) return;

                    const data = r.message;
                    if (!data) {
                        frappe.msgprint(__("Koi data nahi mila."));
                        return;
                    }

                    // ── Top-level scalar fields ko seedha set karo ──────────
                    const scalar_fields = [
                        "module", "naming_rule", "title_field", "search_fields",
                        "description", "image_field", "timeline_field",
                        "nsm_parent_field", "max_attachments", "documentation",
                        "default_print_format", "sort_field", "sort_order",
                        "default_view", "document_type", "icon", "color",
                        "default_email_template", "sender_field", "sender_name_field",
                        "recipient_account_field", "subject_field", "route",
                        "is_published_field", "website_search_field",
                        // Checkboxes
                        "is_submittable", "istable", "issingle", "is_tree",
                        "is_calendar_and_gantt", "editable_grid", "quick_entry",
                        "allow_bulk_edit", "track_changes", "track_seen",
                        "track_views", "custom", "beta", "is_virtual",
                        "queue_in_background", "hide_toolbar", "allow_copy",
                        "allow_import", "allow_events_in_timeline",
                        "allow_auto_repeat", "make_attachments_public",
                        "show_title_field_in_link", "translated_doctype",
                        "show_preview_popup", "show_name_in_global_search",
                        "email_append_to", "read_only", "in_create",
                        "protect_attached_files", "allow_rename",
                        "grid_page_length", "rows_threshold_for_grid_search",
                        "force_re_route_to_default_view", "has_web_view",
                        "allow_guest_to_view", "index_web_pages_for_search",
                        "engine", "row_format",
                    ];

                    scalar_fields.forEach((field) => {
                        if (data[field] !== undefined && frm.fields_dict[field]) {
                            frm.set_value(field, data[field]);
                        }
                    });

                    // ── Child Table: Fields ──────────────────────────────────
                    if (data.fields && frm.fields_dict["fields"]) {
                        frm.clear_table("fields");
                        (data.fields || []).forEach((row) => {
                            const child = frm.add_child("fields");
                            Object.assign(child, row);
                        });
                        frm.refresh_field("fields");
                    }

                    // ── Child Table: Permissions ─────────────────────────────
                    if (data.permissions && frm.fields_dict["permissions"]) {
                        frm.clear_table("permissions");
                        (data.permissions || []).forEach((row) => {
                            const child = frm.add_child("permissions");
                            Object.assign(child, row);
                        });
                        frm.refresh_field("permissions");
                    }

                    // ── Child Table: Actions ─────────────────────────────────
                    if (data.actions && frm.fields_dict["actions"]) {
                        frm.clear_table("actions");
                        (data.actions || []).forEach((row) => {
                            const child = frm.add_child("actions");
                            Object.assign(child, row);
                        });
                        frm.refresh_field("actions");
                    }

                    // ── Child Table: Links ───────────────────────────────────
                    if (data.links && frm.fields_dict["links"]) {
                        frm.clear_table("links");
                        (data.links || []).forEach((row) => {
                            const child = frm.add_child("links");
                            Object.assign(child, row);
                        });
                        frm.refresh_field("links");
                    }

                    // ── Child Table: States ──────────────────────────────────
                    if (data.states && frm.fields_dict["states"]) {
                        frm.clear_table("states");
                        (data.states || []).forEach((row) => {
                            const child = frm.add_child("states");
                            Object.assign(child, row);
                        });
                        frm.refresh_field("states");
                    }

                    frappe.show_alert({
                        message: __("{0} ka data successfully set ho gaya!", [refrence_doctype]),
                        indicator: "green",
                    }, 5);
                },
            });
        }, __("Tools"));
        // ──────────────────────────────────────────────────────────────────
    },
});
