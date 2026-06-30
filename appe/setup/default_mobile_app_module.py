import json

import frappe

DEFAULT_MODULE_NAME = "Appe"

DEFAULT_MODULE_ITEMS = [
	{
		"label": "Live Location Tracker",
		"screen_name": "TraceScreen",
		"image": "/assets/images/location.png",
		"icon_name": "location_on",
	},
	{
		"label": "User Activity",
		"screen_name": "EmployeeTimelineScreen",
		"image": "/assets/images/timeline.png",
		"icon_name": "history",
	},
	{
		"label": "Local Sync Data",
		"screen_name": "LocalSyncQueueScreen",
		"image": "/assets/images/sync.png",
		"icon_name": "cloud_upload",
	},
	{
		"label": "Reports",
		"screen_name": "ReportScreen",
		"image": "/assets/images/reports.png",
		"icon_name": "analytics",
	},
	{
		"label": "Shop",
		"screen_name": "EcommerceScreen",
		"image": "/assets/images/shop.png",
		"icon_name": "shopping_cart",
		"erpnext_only": True,
	},
	{
		"label": "Sales Order",
		"screen_name": "SalesOrderScreen",
		"image": "/assets/images/shop.png",
		"icon_name": "receipt_long",
		"erpnext_only": True,
	},
	{
		"label": "Dashboard",
		"screen_name": "MyDashboardScreen",
		"image": "/assets/images/dashboard.png",
		"icon_name": "dashboard",
	},
	{
		"label": "Workspace",
		"screen_name": "WorkspaceScreen",
		"image": "/assets/images/workspace.png",
		"icon_name": "workspace_premium",
	},
	{
		"label": "Screens",
		"screen_name": "ScreensScreen",
		"image": "/assets/images/screens.png",
		"icon_name": "view_carousel",
	},
]


def _is_erpnext_installed():
	return "erpnext" in frappe.get_installed_apps()


def _build_module_item_row(item: dict) -> dict:
	return {
		"doctype": "Mobile App Module Items",
		"label": item["label"],
		"type": "Screen",
		"refrence_doctype": "Appe Screen",
		"screen_name": item["screen_name"],
		"image": item.get("image") or "",
		"json": json.dumps({"icon_name": item.get("icon_name") or ""}),
		"active": 1,
	}


def create_default_mobile_app_module():
	"""Seed the built-in Appe mobile module (skip if module_name already exists)."""
	if frappe.db.exists("Mobile App Module", {"module_name": DEFAULT_MODULE_NAME}):
		return {"created": 0, "skipped": 1, "module_name": DEFAULT_MODULE_NAME}

	items = []
	for item in DEFAULT_MODULE_ITEMS:
		if item.get("erpnext_only") and not _is_erpnext_installed():
			continue
		items.append(_build_module_item_row(item))

	doc = frappe.get_doc(
		{
			"doctype": "Mobile App Module",
			"module_name": DEFAULT_MODULE_NAME,
			"image": "../assets/images/appe.png",
			"sequence_id": 1,
			"items": items,
		}
	)
	doc.insert(ignore_permissions=True)

	return {
		"created": 1,
		"skipped": 0,
		"module_name": DEFAULT_MODULE_NAME,
		"items_added": len(items),
	}
