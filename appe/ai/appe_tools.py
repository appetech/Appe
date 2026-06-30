from __future__ import annotations

import json
from typing import Any

import frappe

from .tools import (
	Tool,
	_check_user_can,
	_ensure_capability,
	register,
)


# ---------------------------------------------------------------------------
# Capability helper — mobile config creation uses allow_create_workspace flag
# ---------------------------------------------------------------------------


def _ensure_mobile_create(tool_name: str):
	_ensure_capability("allow_create_workspace", tool_name)


def _ensure_mobile_read(tool_name: str):
	_ensure_capability("allow_query_data", tool_name)


# ---------------------------------------------------------------------------
# Item builders — normalize AI input to child-table row dicts
# ---------------------------------------------------------------------------

_MODULE_TYPE_DOCTYPE = {
	"Doctype": None,  # user supplies refrence_doctype
	"Form": None,
	"Single Doctype": None,
	"Report": "Appe Report",
	"Screen": "Appe Screen",
	"Dashboard": "Dashboard",
	"Workspace": "Workspace",
	"WebPage": None,
}

_DASHBOARD_TYPE_DOCTYPE = {
	"Doctype": None,
	"Form": None,
	"Single Doctype": None,
	"Report": "Appe Report",
	"Screen": "Appe Screen",
	"Dashboard": "Dashboard",
	"WebPage": None,
	"Chart": "Dashboard Chart",
	"Number Card": "Number Card",
}


def _build_module_item(item: dict) -> dict:
	itype = (item.get("type") or "").strip()
	if not itype:
		raise ValueError("Each item needs a 'type'")
	label = (item.get("label") or itype).strip()
	row: dict[str, Any] = {
		"doctype": "Mobile App Module Items",
		"label": label,
		"type": itype,
		"active": 1 if item.get("active", True) else 0,
	}
	if item.get("description"):
		row["description"] = item["description"]
	if item.get("image"):
		row["image"] = item["image"]
	if item.get("json"):
		row["json"] = item["json"] if isinstance(item["json"], str) else json.dumps(item["json"])

	auto_dt = _MODULE_TYPE_DOCTYPE.get(itype)
	if auto_dt:
		row["refrence_doctype"] = item.get("refrence_doctype") or auto_dt
	else:
		if item.get("refrence_doctype"):
			row["refrence_doctype"] = item["refrence_doctype"]
	if item.get("refrence_docname"):
		row["refrence_docname"] = item["refrence_docname"]
	if itype == "Report":
		if not item.get("report_name"):
			raise ValueError(f"Item '{label}': type=Report requires report_name (Appe Report name)")
		row["report_name"] = item["report_name"]
	if itype == "Screen":
		screen = item.get("screen_name") or item.get("route")
		if not screen:
			# Try to resolve from Appe Screen doc
			screen_doc = item.get("refrence_docname") or item.get("appe_screen")
			if screen_doc and frappe.db.exists("Appe Screen", screen_doc):
				screen = frappe.db.get_value("Appe Screen", screen_doc, "route") or screen_doc
		if not screen:
			raise ValueError(f"Item '{label}': type=Screen requires screen_name or route")
		row["screen_name"] = screen
		row.setdefault("refrence_doctype", "Appe Screen")
	if itype == "WebPage":
		if not item.get("web_url"):
			raise ValueError(f"Item '{label}': type=WebPage requires web_url")
		row["web_url"] = item["web_url"]
	return row


def _build_dashboard_item(item: dict) -> dict:
	itype = (item.get("type") or "").strip()
	if not itype:
		raise ValueError("Each item needs a 'type'")
	label = (item.get("label") or itype).strip()
	row: dict[str, Any] = {
		"doctype": "Mobile App Dashboard Items",
		"label": label,
		"type": itype,
		"active": 1 if item.get("active", True) else 0,
	}
	if item.get("image"):
		row["image"] = item["image"]
	if item.get("json"):
		row["json"] = item["json"] if isinstance(item["json"], str) else json.dumps(item["json"])

	auto_dt = _DASHBOARD_TYPE_DOCTYPE.get(itype)
	if auto_dt:
		row["linked_doctype"] = item.get("linked_doctype") or auto_dt
	else:
		if item.get("linked_doctype"):
			row["linked_doctype"] = item["linked_doctype"]
	if item.get("refrence_docname"):
		row["refrence_docname"] = item["refrence_docname"]
	if itype == "Report":
		if not item.get("report_name"):
			raise ValueError(f"Item '{label}': type=Report requires report_name")
		row["report_name"] = item["report_name"]
	if itype == "Screen":
		screen = item.get("screen_name") or item.get("route")
		if not screen:
			screen_doc = item.get("refrence_docname") or item.get("appe_screen")
			if screen_doc and frappe.db.exists("Appe Screen", screen_doc):
				screen = frappe.db.get_value("Appe Screen", screen_doc, "route") or screen_doc
		if not screen:
			raise ValueError(f"Item '{label}': type=Screen requires screen_name or route")
		row["screen_name"] = screen
		row.setdefault("linked_doctype", "Appe Screen")
	if itype == "WebPage":
		if not item.get("web_url"):
			raise ValueError(f"Item '{label}': type=WebPage requires web_url")
		row["web_url"] = item["web_url"]
	if itype in ("Chart", "Number Card", "Dashboard") and item.get("refrence_docname"):
		row["refrence_docname"] = item["refrence_docname"]
	return row


def _build_appe_report_filter(f: dict) -> dict:
	return {
		"doctype": "DocField",
		"fieldname": f.get("fieldname") or f.get("field_name"),
		"label": f.get("label") or (f.get("fieldname") or "").replace("_", " ").title(),
		"fieldtype": f.get("fieldtype") or "Data",
		"options": f.get("options") or "",
		"reqd": 1 if f.get("reqd") else 0,
	}


def _build_appe_report_column(c: dict) -> dict:
	return {
		"doctype": "Appe Report Column",
		"column_fieldname": c.get("column_fieldname") or c.get("fieldname"),
		"column_label": c.get("column_label") or c.get("label") or "",
		"position": c.get("position") or "Left",
		"is_bold": 1 if c.get("is_bold") else 0,
		"font_size": c.get("font_size") or "Medium",
	}


def _default_appe_print_format() -> str | None:
	"""Find a Print Format usable for Appe Prepared Report."""
	pf = frappe.db.get_value(
		"Print Format",
		{"doc_type": "Appe Prepared Report", "disabled": 0},
		"name",
	)
	if pf:
		return pf
	# Fallback: any print format for Appe Prepared Report
	pf = frappe.db.get_value("Print Format", {"doc_type": "Appe Prepared Report"}, "name")
	return pf


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


def _h_get_mobile_app_config(args: dict, ctx: dict) -> dict:
	"""Mirror of appe_api.get_module_data + get_dashboard_sections for AI."""
	_ensure_mobile_read("get_mobile_app_config")
	_check_user_can("read", "Mobile App Module")
	_check_user_can("read", "Mobile App Dashboard")

	modules = frappe.get_all(
		"Mobile App Module",
		fields=["name", "module_name", "image", "sequence_id"],
		order_by="sequence_id asc",
	)
	module_data = []
	for mod in modules:
		items = frappe.get_all(
			"Mobile App Module Items",
			filters={"parent": mod.name, "active": 1},
			fields=[
				"label", "type", "refrence_doctype", "refrence_docname",
				"report_name", "screen_name", "web_url", "description", "active",
			],
		)
		module_data.append({**mod, "items": items})

	sections = frappe.get_all(
		"Mobile App Dashboard",
		filters={"status": "Active"},
		fields=["name", "section_name", "section_view", "sequence_id", "hide_section_name", "status"],
		order_by="sequence_id asc",
	)
	dashboard_data = []
	for sec in sections:
		items = frappe.get_all(
			"Mobile App Dashboard Items",
			filters={"parent": sec.name},
			fields=[
				"label", "type", "linked_doctype", "refrence_docname",
				"report_name", "screen_name", "web_url", "active",
			],
		)
		dashboard_data.append({**sec, "items": items})

	return {
		"modules": module_data,
		"module_count": len(module_data),
		"dashboard_sections": dashboard_data,
		"dashboard_section_count": len(dashboard_data),
		"note": "Mobile app reads this via get_module_data and get_dashboard_sections APIs. Tell user to refresh mobile app after changes.",
	}


def _h_list_appe_reports(args: dict, ctx: dict) -> dict:
	_ensure_mobile_read("list_appe_reports")
	_check_user_can("read", "Appe Report")
	keyword = (args.get("keyword") or "").strip()
	filters: dict = {"disabled": 0}
	if keyword:
		filters["report_name"] = ["like", f"%{keyword}%"]
	rows = frappe.get_all(
		"Appe Report",
		filters=filters,
		fields=["name", "report_name", "report", "orientation", "description", "disabled"],
		order_by="modified desc",
		limit=min(int(args.get("limit") or 50), 100),
	)
	return {"count": len(rows), "reports": rows}


def _h_get_appe_report(args: dict, ctx: dict) -> dict:
	_ensure_mobile_read("get_appe_report")
	_check_user_can("read", "Appe Report")
	name = args.get("name") or args.get("report_name")
	if not name:
		raise ValueError("name or report_name is required")
	if not frappe.db.exists("Appe Report", name):
		raise ValueError(f"Appe Report '{name}' not found")
	doc = frappe.get_doc("Appe Report", name)
	filters = [
		{"fieldname": f.fieldname, "label": f.label, "fieldtype": f.fieldtype, "reqd": f.reqd}
		for f in (doc.filters or [])
	]
	columns = [
		{
			"column_fieldname": c.column_fieldname,
			"column_label": c.column_label,
			"position": c.position,
			"font_size": c.font_size,
		}
		for c in (doc.column or [])
	]
	return {
		"name": doc.name,
		"report_name": doc.report_name,
		"report": doc.report,
		"orientation": doc.orientation,
		"description": doc.description,
		"disabled": int(doc.disabled or 0),
		"filters": filters,
		"columns": columns,
	}


def _h_list_appe_screens(args: dict, ctx: dict) -> dict:
	_ensure_mobile_read("list_appe_screens")
	_check_user_can("read", "Appe Screen")
	keyword = (args.get("keyword") or "").strip()
	filters: dict = {}
	if keyword:
		filters["screen_name"] = ["like", f"%{keyword}%"]
	rows = frappe.get_all(
		"Appe Screen",
		filters=filters,
		fields=["name", "screen_name", "route", "is_group", "parent_appe_screen", "description"],
		order_by="lft asc",
		limit=min(int(args.get("limit") or 100), 200),
	)
	return {"count": len(rows), "screens": rows}


def _h_get_appe_settings_public(args: dict, ctx: dict) -> dict:
	_ensure_mobile_read("get_appe_settings_public")
	_check_user_can("read", "Appe Settings")
	doc = frappe.get_single("Appe Settings")
	return {
		"enable_checkin": int(doc.enable_checkin or 0),
		"enable_checkin_with_faceid": int(doc.enable_checkin_with_faceid or 0),
		"enable_live_location_tracking": int(doc.enable_live_location_tracking or 0),
		"enable_home_tabs": int(doc.enable_home_tabs or 0),
		"enable_approval_requests": int(doc.enable_approval_requests or 0),
		"enable_attendance": int(doc.enable_attendance or 0),
		"enable_leave_balance": int(doc.enable_leave_balance or 0),
		"hide_column_break": int(doc.hide_column_break or 0),
		"hide_tab_break": int(doc.hide_tab_break or 0),
		"site_name": doc.site_name,
		"note": "Secrets (OneSignal, Google Maps API keys) are not exposed.",
	}


def _h_list_appe_doctypes(args: dict, ctx: dict) -> dict:
	"""List all DocTypes in the Appe module with brief purpose."""
	_ensure_mobile_read("list_appe_doctypes")
	_check_user_can("read", "DocType")
	rows = frappe.get_all(
		"DocType",
		filters={"module": ["in", ["Appe", "appe"]], "istable": 0},
		fields=["name", "issingle", "is_submittable", "is_tree"],
		order_by="name asc",
	)
	purposes = {
		"Mobile App Module": "Bottom navigation modules for mobile app",
		"Mobile App Dashboard": "Home screen sections for mobile app",
		"Appe Report": "Mobile report wrapper around Frappe Report",
		"Appe Screen": "Custom mobile screens with routes",
		"Appe Settings": "Global mobile app toggles (single)",
		"Appe API Integration": "Remote Frappe site connection for reports",
		"Appe Prepared Report": "Report execution queue/results",
		"Appe Doctype Action Button": "Custom action buttons on mobile forms",
		"Mobile App Notification": "Push notifications",
		"Appe Buddy Settings": "AI assistant configuration",
		"Appe Buddy Conversation": "AI chat sessions",
		"Appe Employee": "Employee master (standalone mode)",
		"Appe Customer": "Customer master (standalone mode)",
		"Appe Check-in": "Field check-in (standalone mode)",
		"Appe Attendance": "Attendance records",
		"Appe Chat": "In-app messaging",
		"Appe Post": "Social feed posts",
		"Appe Expense": "Expense claims",
		"Employee Location": "GPS location tracking",
	}
	for r in rows:
		r["purpose"] = purposes.get(r["name"], "Appe module DocType")
	return {"count": len(rows), "doctypes": rows}


# ---------------------------------------------------------------------------
# Create / update handlers
# ---------------------------------------------------------------------------


def _h_create_mobile_module(args: dict, ctx: dict) -> dict:
	_ensure_mobile_create("create_mobile_module")
	_check_user_can("create", "Mobile App Module")
	module_name = (args.get("module_name") or "").strip()
	if not module_name:
		raise ValueError("module_name is required")
	items_in = args.get("items") or []
	if not items_in:
		raise ValueError("items is required — at least one Mobile App Module Item")

	child_rows = [_build_module_item(i) for i in items_in]
	doc = frappe.get_doc(
		{
			"doctype": "Mobile App Module",
			"module_name": module_name,
			"sequence_id": int(args.get("sequence_id") or 0),
			"items": child_rows,
		}
	)
	if args.get("image"):
		doc.image = args["image"]
	doc.insert(ignore_permissions=False)
	return {
		"name": doc.name,
		"module_name": doc.module_name,
		"items_added": len(child_rows),
		"note": "Refresh the mobile app to see the new module.",
	}


def _h_update_mobile_module(args: dict, ctx: dict) -> dict:
	_ensure_mobile_create("update_mobile_module")
	_check_user_can("write", "Mobile App Module")
	name = args.get("name") or args.get("module_name")
	if not name:
		raise ValueError("name (Mobile App Module record name) is required")
	if not frappe.db.exists("Mobile App Module", name):
		# Try lookup by module_name
		name = frappe.db.get_value("Mobile App Module", {"module_name": name}, "name")
		if not name:
			raise ValueError("Mobile App Module not found")
	doc = frappe.get_doc("Mobile App Module", name)
	if args.get("module_name"):
		doc.module_name = args["module_name"]
	if args.get("sequence_id") is not None:
		doc.sequence_id = int(args["sequence_id"])
	if args.get("image"):
		doc.image = args["image"]
	if args.get("items") is not None:
		mode = (args.get("items_mode") or "replace").lower()
		new_rows = [_build_module_item(i) for i in (args.get("items") or [])]
		if mode == "append":
			doc.extend("items", new_rows)
		else:
			doc.set("items", new_rows)
	doc.save(ignore_permissions=False)
	return {
		"name": doc.name,
		"module_name": doc.module_name,
		"item_count": len(doc.items or []),
		"note": "Refresh the mobile app to see changes.",
	}


def _h_create_mobile_dashboard(args: dict, ctx: dict) -> dict:
	_ensure_mobile_create("create_mobile_dashboard")
	_check_user_can("create", "Mobile App Dashboard")
	section_name = (args.get("section_name") or "").strip()
	if not section_name:
		raise ValueError("section_name is required")
	section_view = (args.get("section_view") or "Grid View").strip()
	items_in = args.get("items") or []
	if not items_in:
		raise ValueError("items is required — at least one dashboard item")

	child_rows = [_build_dashboard_item(i) for i in items_in]
	doc = frappe.get_doc(
		{
			"doctype": "Mobile App Dashboard",
			"section_name": section_name,
			"section_view": section_view,
			"status": args.get("status") or "Active",
			"sequence_id": int(args.get("sequence_id") or 0),
			"hide_section_name": 1 if args.get("hide_section_name") else 0,
			"items": child_rows,
		}
	)
	doc.insert(ignore_permissions=False)
	return {
		"name": doc.name,
		"section_name": doc.section_name,
		"section_view": doc.section_view,
		"items_added": len(child_rows),
		"note": "Refresh the mobile app home screen to see the new section.",
	}


def _h_update_mobile_dashboard(args: dict, ctx: dict) -> dict:
	_ensure_mobile_create("update_mobile_dashboard")
	_check_user_can("write", "Mobile App Dashboard")
	name = args.get("name") or args.get("section_name")
	if not name:
		raise ValueError("name is required")
	if not frappe.db.exists("Mobile App Dashboard", name):
		name = frappe.db.get_value("Mobile App Dashboard", {"section_name": name}, "name")
		if not name:
			raise ValueError("Mobile App Dashboard section not found")
	doc = frappe.get_doc("Mobile App Dashboard", name)
	for field in ("section_name", "section_view", "status"):
		if args.get(field):
			doc.set(field, args[field])
	if args.get("sequence_id") is not None:
		doc.sequence_id = int(args["sequence_id"])
	if args.get("hide_section_name") is not None:
		doc.hide_section_name = 1 if args["hide_section_name"] else 0
	if args.get("items") is not None:
		mode = (args.get("items_mode") or "replace").lower()
		new_rows = [_build_dashboard_item(i) for i in (args.get("items") or [])]
		if mode == "append":
			doc.extend("items", new_rows)
		else:
			doc.set("items", new_rows)
	doc.save(ignore_permissions=False)
	return {
		"name": doc.name,
		"section_name": doc.section_name,
		"status": doc.status,
		"item_count": len(doc.items or []),
		"note": "Refresh the mobile app to see changes.",
	}


def _h_create_appe_report(args: dict, ctx: dict) -> dict:
	_ensure_mobile_create("create_appe_report")
	_check_user_can("create", "Appe Report")
	report_name = (args.get("report_name") or "").strip()
	if not report_name:
		raise ValueError("report_name is required (unique mobile display name)")
	if frappe.db.exists("Appe Report", report_name):
		raise ValueError(f"Appe Report '{report_name}' already exists")

	frappe_report = (args.get("report") or "").strip()
	if not frappe_report and not args.get("appe_api_integration"):
		raise ValueError("report (Frappe Report name) is required unless using appe_api_integration")
	if frappe_report and not frappe.db.exists("Report", frappe_report):
		raise ValueError(f"Frappe Report '{frappe_report}' not found — create it first with create_report")

	print_format = args.get("print_format") or _default_appe_print_format()
	if not print_format:
		raise ValueError(
			"No Print Format found for 'Appe Prepared Report'. "
			"Ask admin to create one in Print Format list first."
		)

	filters_in = args.get("filters") or []
	columns_in = args.get("columns") or args.get("column") or []

	# Auto-build columns from Frappe report if none supplied
	if not columns_in and frappe_report:
		try:
			from frappe.desk.query_report import run as run_query_report
			result = run_query_report(report_name=frappe_report, filters={}, user=frappe.session.user)
			for col in (result.get("columns") or [])[:20]:
				fieldname = col.get("fieldname") or col.get("field") or str(col)
				columns_in.append(
					{"column_fieldname": fieldname, "column_label": col.get("label") or fieldname}
				)
		except Exception:
			pass

	if not filters_in:
		# Minimal default filter row so validation passes
		filters_in = [{"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Company"}]

	doc = frappe.get_doc(
		{
			"doctype": "Appe Report",
			"report_name": report_name,
			"report": frappe_report,
			"orientation": args.get("orientation") or "Portrait",
			"description": args.get("description") or "",
			"print_format": print_format,
			"disabled": 0,
			"filters": [_build_appe_report_filter(f) for f in filters_in],
			"column": [_build_appe_report_column(c) for c in columns_in] if columns_in else [],
		}
	)
	if args.get("appe_api_integration"):
		doc.appe_api_integration = args["appe_api_integration"]
		doc.third_party_report_name = args.get("third_party_report_name") or ""
	doc.insert(ignore_permissions=False)
	return {
		"name": doc.name,
		"report_name": doc.report_name,
		"report": doc.report,
		"filters_count": len(doc.filters or []),
		"columns_count": len(doc.column or []),
		"note": "Link this Appe Report in a Mobile App Module/Dashboard item with type=Report.",
	}


def _h_create_appe_screen(args: dict, ctx: dict) -> dict:
	_ensure_mobile_create("create_appe_screen")
	_check_user_can("create", "Appe Screen")
	screen_name = (args.get("screen_name") or "").strip()
	route = (args.get("route") or "").strip()
	if not screen_name:
		raise ValueError("screen_name is required")
	if not route:
		route = "/" + screen_name.lower().replace(" ", "-")

	doc = frappe.get_doc(
		{
			"doctype": "Appe Screen",
			"screen_name": screen_name,
			"route": route,
			"is_group": 1 if args.get("is_group") else 0,
			"description": args.get("description") or "",
		}
	)
	if args.get("parent_appe_screen"):
		doc.parent_appe_screen = args["parent_appe_screen"]
	if args.get("page"):
		doc.page = args["page"]
	if args.get("image"):
		doc.image = args["image"]
	doc.insert(ignore_permissions=False)
	return {
		"name": doc.name,
		"screen_name": doc.screen_name,
		"route": doc.route,
		"note": f"Use screen_name='{doc.route}' when linking in module/dashboard items with type=Screen.",
	}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_appe_tools():
	register(
		Tool(
			name="get_mobile_app_config",
			description=(
				"Read the current mobile app configuration: all Mobile App Modules "
				"(bottom nav) and active Mobile App Dashboard sections (home screen). "
				"Use this FIRST when user asks about mobile app layout or what's configured."
			),
			parameters={"type": "object", "properties": {}},
			handler=_h_get_mobile_app_config,
		)
	)
	register(
		Tool(
			name="list_appe_reports",
			description="List Appe Reports configured for the mobile app.",
			parameters={
				"type": "object",
				"properties": {
					"keyword": {"type": "string"},
					"limit": {"type": "integer", "default": 50},
				},
			},
			handler=_h_list_appe_reports,
		)
	)
	register(
		Tool(
			name="get_appe_report",
			description="Get full details of one Appe Report including filters and columns.",
			parameters={
				"type": "object",
				"properties": {
					"name": {"type": "string", "description": "Appe Report name"},
					"report_name": {"type": "string"},
				},
			},
			handler=_h_get_appe_report,
		)
	)
	register(
		Tool(
			name="list_appe_screens",
			description="List Appe Screen records with their mobile route strings.",
			parameters={
				"type": "object",
				"properties": {
					"keyword": {"type": "string"},
					"limit": {"type": "integer", "default": 100},
				},
			},
			handler=_h_list_appe_screens,
		)
	)
	register(
		Tool(
			name="get_appe_settings_public",
			description=(
				"Read public Appe Settings flags (check-in, location tracking, attendance, etc.). "
				"Does NOT expose API keys."
			),
			parameters={"type": "object", "properties": {}},
			handler=_h_get_appe_settings_public,
		)
	)
	register(
		Tool(
			name="list_appe_doctypes",
			description="List all DocTypes in the Appe module with their purpose — use when explaining Appe features to users.",
			parameters={"type": "object", "properties": {}},
			handler=_h_list_appe_doctypes,
		)
	)
	register(
		Tool(
			name="create_mobile_module",
			description=(
				"Create a new Mobile App Module (bottom navigation tab) for the Flutter mobile app. "
				"Each item in `items` needs: label, type (Doctype/Report/Screen/WebPage/Dashboard/Workspace/Form), "
				"and type-specific fields (refrence_doctype, report_name, screen_name, web_url)."
			),
			parameters={
				"type": "object",
				"properties": {
					"module_name": {"type": "string"},
					"sequence_id": {"type": "integer", "default": 0},
					"image": {"type": "string", "description": "Attach Image URL/path"},
					"items": {
						"type": "array",
						"items": {
							"type": "object",
							"additionalProperties": True,
							"properties": {
								"label": {"type": "string"},
								"type": {"type": "string"},
								"refrence_doctype": {"type": "string"},
								"refrence_docname": {"type": "string"},
								"report_name": {"type": "string"},
								"screen_name": {"type": "string"},
								"route": {"type": "string"},
								"web_url": {"type": "string"},
								"description": {"type": "string"},
								"active": {"type": "boolean", "default": True},
							},
							"required": ["label", "type"],
						},
					},
				},
				"required": ["module_name", "items"],
			},
			handler=_h_create_mobile_module,
		)
	)
	register(
		Tool(
			name="update_mobile_module",
			description=(
				"Update an existing Mobile App Module. Pass `name` (record id) or module_name. "
				"Use items_mode='append' to add items without replacing existing ones."
			),
			parameters={
				"type": "object",
				"properties": {
					"name": {"type": "string"},
					"module_name": {"type": "string"},
					"sequence_id": {"type": "integer"},
					"image": {"type": "string"},
					"items_mode": {"type": "string", "enum": ["replace", "append"], "default": "replace"},
					"items": {
						"type": "array",
						"items": {"type": "object", "additionalProperties": True},
					},
				},
				"required": [],
			},
			handler=_h_update_mobile_module,
		)
	)
	register(
		Tool(
			name="create_mobile_dashboard",
			description=(
				"Create a new Mobile App Dashboard section (home screen block) for the mobile app. "
				"section_view controls layout: Grid View, List View, Chart View, Number Card View, etc. "
				"Dashboard items use linked_doctype (not refrence_doctype)."
			),
			parameters={
				"type": "object",
				"properties": {
					"section_name": {"type": "string"},
					"section_view": {
						"type": "string",
						"enum": [
							"Grid View", "Horizontal Scrollable View", "Chart View",
							"Number Card View", "Banner View", "Image Grid View",
							"Doctype Card Horizontal View", "Doctype Card List View",
							"List View", "Calendar View",
						],
						"default": "Grid View",
					},
					"status": {"type": "string", "enum": ["Active", "Disable"], "default": "Active"},
					"sequence_id": {"type": "integer", "default": 0},
					"hide_section_name": {"type": "boolean", "default": False},
					"items": {
						"type": "array",
						"items": {
							"type": "object",
							"additionalProperties": True,
							"properties": {
								"label": {"type": "string"},
								"type": {"type": "string"},
								"linked_doctype": {"type": "string"},
								"refrence_docname": {"type": "string"},
								"report_name": {"type": "string"},
								"screen_name": {"type": "string"},
								"web_url": {"type": "string"},
								"active": {"type": "boolean", "default": True},
							},
							"required": ["label", "type"],
						},
					},
				},
				"required": ["section_name", "items"],
			},
			handler=_h_create_mobile_dashboard,
		)
	)
	register(
		Tool(
			name="update_mobile_dashboard",
			description=(
				"Update an existing Mobile App Dashboard section. "
				"Set status='Disable' to hide without deleting. Use items_mode='append' to add items."
			),
			parameters={
				"type": "object",
				"properties": {
					"name": {"type": "string"},
					"section_name": {"type": "string"},
					"section_view": {"type": "string"},
					"status": {"type": "string", "enum": ["Active", "Disable"]},
					"sequence_id": {"type": "integer"},
					"hide_section_name": {"type": "boolean"},
					"items_mode": {"type": "string", "enum": ["replace", "append"], "default": "replace"},
					"items": {
						"type": "array",
						"items": {"type": "object", "additionalProperties": True},
					},
				},
				"required": [],
			},
			handler=_h_update_mobile_dashboard,
		)
	)
	register(
		Tool(
			name="create_appe_report",
			description=(
				"Create an Appe Report for the mobile app, wrapping an existing Frappe Report. "
				"After creation, link it in a module/dashboard item with type=Report and report_name=<this name>. "
				"If columns omitted, auto-detected from the Frappe report output."
			),
			parameters={
				"type": "object",
				"properties": {
					"report_name": {"type": "string", "description": "Unique mobile display name"},
					"report": {"type": "string", "description": "Frappe Report name to wrap"},
					"orientation": {"type": "string", "enum": ["Portrait", "Landscape"], "default": "Portrait"},
					"description": {"type": "string"},
					"print_format": {"type": "string"},
					"filters": {
						"type": "array",
						"items": {
							"type": "object",
							"additionalProperties": True,
							"properties": {
								"fieldname": {"type": "string"},
								"label": {"type": "string"},
								"fieldtype": {"type": "string"},
								"options": {"type": "string"},
								"reqd": {"type": "boolean"},
							},
						},
					},
					"columns": {
						"type": "array",
						"items": {
							"type": "object",
							"additionalProperties": True,
							"properties": {
								"column_fieldname": {"type": "string"},
								"column_label": {"type": "string"},
								"position": {"type": "string", "enum": ["Left", "Right", "Center"]},
								"font_size": {"type": "string", "enum": ["Small", "Medium", "Large"]},
								"is_bold": {"type": "boolean"},
							},
						},
					},
				},
				"required": ["report_name", "report"],
			},
			handler=_h_create_appe_report,
		)
	)
	register(
		Tool(
			name="create_appe_screen",
			description=(
				"Create an Appe Screen with a mobile route. "
				"Use the returned route as screen_name when linking in module/dashboard items."
			),
			parameters={
				"type": "object",
				"properties": {
					"screen_name": {"type": "string"},
					"route": {"type": "string", "description": "Mobile route e.g. /sales/orders"},
					"description": {"type": "string"},
					"is_group": {"type": "boolean", "default": False},
					"parent_appe_screen": {"type": "string"},
					"page": {"type": "string", "description": "Optional Frappe Page link"},
					"image": {"type": "string"},
				},
				"required": ["screen_name"],
			},
			handler=_h_create_appe_screen,
		)
	)


register_appe_tools()
