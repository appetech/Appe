frappe.listview_settings["Appe Screen"] = {
	onload(listview) {
		if (!frappe.model.can_create("Appe Screen")) {
			return;
		}

		listview.page.add_inner_button(__("Fetch Default Screens"), () => {
			frappe.call({
				method: "appe.appe.doctype.appe_screen.appe_screen.fetch_default_screens",
				freeze: true,
				freeze_message: __("Fetching default screens..."),
				callback(r) {
					if (!r.message) {
						return;
					}

					const { created, skipped, total } = r.message;
					frappe.msgprint({
						title: __("Default Screens"),
						message: __(
							"Created: {0}, Already existed: {1}, Total built-in: {2}",
							[created, skipped, total]
						),
						indicator: created ? "green" : "blue",
					});
					listview.refresh();
				},
			});
		});
	},
};
