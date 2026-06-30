import frappe

# Flutter named routes → display labels for Appe Screen records.
DEFAULT_APPE_SCREENS = [
	{"route": "TraceScreen", "screen_name": "Trace"},
	{"route": "TrainingScreen", "screen_name": "Training"},
	{"route": "ReportScreen", "screen_name": "Report"},
	{"route": "CategoryScreen", "screen_name": "Category"},
	{"route": "EcommerceScreen", "screen_name": "Ecommerce"},
	{"route": "SalesOrderScreen", "screen_name": "Sales Order"},
	{"route": "MyDashboardScreen", "screen_name": "My Dashboard"},
	{"route": "WorkspaceScreen", "screen_name": "Workspace"},
	{"route": "ScreensScreen", "screen_name": "Screens"},
	{"route": "EmployeeTimelineScreen", "screen_name": "My Timeline"},
	{"route": "LocalSyncQueueScreen", "screen_name": "Local Sync Queue"},
	{"route": "EmployeeProfileScreen", "screen_name": "My EmployeeProfile"},
	{"route": "ChatListScreen", "screen_name": "Chat List"},
	{"route": "UpdatesScreen", "screen_name": "Updates"},
	{"route": "ModuleCategoriesScreen", "screen_name": "Module Categories"},
	{"route": "ProfileScreen", "screen_name": "My Profile"},
	{"route": "UpdateScreen", "screen_name": "Update"},
]


def create_default_appe_screens():
	"""Seed built-in Flutter screens as Appe Screen records (skip existing routes)."""
	created = 0
	skipped = 0

	for screen in DEFAULT_APPE_SCREENS:
		route = screen["route"]
		if frappe.db.exists("Appe Screen", {"route": route}):
			skipped += 1
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Appe Screen",
				"screen_name": screen["screen_name"],
				"route": route,
				"is_group": 0,
			}
		)
		doc.insert(ignore_permissions=True)
		created += 1

	return {
		"created": created,
		"skipped": skipped,
		"total": len(DEFAULT_APPE_SCREENS),
	}
