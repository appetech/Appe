// Copyright (c) 2026, Appe Technologies and contributors
// For license information, please see license.txt

frappe.treeview_settings["Appe Category"] = {
	breadcrumb: "Appe Shop",
	title: "Appe Category",
	get_tree_root: true,
	filters: [
		{
			fieldname: "status",
			fieldtype: "Select",
			options: "\nActive\nDisabled",
			label: __("Status"),
		},
	],
	fields: [
		{
			fieldtype: "Data",
			fieldname: "category",
			label: __("Category"),
			reqd: true,
		},
		{
			fieldtype: "Check",
			fieldname: "is_group",
			label: __("Is Group"),
		},
		{
			fieldtype: "Check",
			fieldname: "show_in_home_screen",
			label: __("Show in Home Screen"),
		},
	],
};
