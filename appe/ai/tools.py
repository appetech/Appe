
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import frappe
from frappe.utils import cstr


# ---------------------------------------------------------------------------
# Capability helpers
# ---------------------------------------------------------------------------


def _settings():
	return frappe.get_cached_doc("Appe Buddy Settings")


def _ensure_capability(flag: str, tool_name: str):
	settings = _settings()
	if not getattr(settings, flag, 0):
		raise PermissionError(f"Capability '{flag}' is disabled for tool '{tool_name}' in Appe Buddy Settings")


def _ensure_doctype_allowed(doctype: str):
	if not doctype:
		raise ValueError("doctype is required")
	blocked = _settings().get_blocked_doctypes()
	# Block obvious sensitive doctypes by default
	hard_blocked = {
		# Frappe core security / permissions
		"User",
		"User Permission",
		"Role",
		"Role Profile",
		"Custom Role",
		"DocPerm",
		"Custom DocPerm",
		"Server Script",
		"Client Script",
		"OAuth Bearer Token",
		"OAuth Authorization Code",
		"OAuth Provider Settings",
		"Workflow Action Permitted Role",
		"Appe Buddy Settings",
		"Appe Buddy Tool Log",
		"System Settings",
		"Website Settings",
		# Frappe internals never edited via AI
		"Email Account",
		"Email Domain",
		"Communication",
		"Auto Email Report",
		"Backup Manager Settings",
		"Webhook",
		"Notification Settings",
		"LDAP Settings",
		"Social Login Key",
		"Domain Settings",
		# ERPNext sensitive: GL/SLE are derived ledgers — never written directly
		"GL Entry",
		"Stock Ledger Entry",
		"Period Closing Voucher",
		"Repost Item Valuation",
		"Process Deferred Accounting",
		"Cost Center Allocation",
	}
	if doctype in hard_blocked or doctype in blocked:
		raise PermissionError(f"DocType '{doctype}' is blocked for Appe Buddy")


def _check_user_can(ptype: str, doctype: str):
	if not frappe.has_permission(doctype, ptype=ptype):
		raise PermissionError(f"You do not have {ptype} permission on {doctype}")


def _user_has_unrestricted_access(doctype: str) -> bool:
	"""True when the current user has no row-level restrictions on `doctype`.

	Aggregate SQL tools require this — if a user can only see *some* records
	(e.g. via User Permission on Company / Customer), running raw SUM() would
	leak hidden rows. We refuse the aggregate and ask the user to use the
	row-by-row tools instead, which honour permissions automatically.
	"""
	user = frappe.session.user
	if user == "Administrator":
		return True
	if "System Manager" in frappe.get_roles(user):
		return True
	# If there are user permissions defined for this doctype, treat as
	# restricted. (Conservative — better to deny aggregate than leak.)
	try:
		from frappe.permissions import get_doctypes_with_read_perm  # type: ignore  # noqa
	except Exception:
		pass
	# Cheap test: are there any User Permission rows for the user that limit
	# this doctype OR a doctype that this one filters by?
	if frappe.db.exists("User Permission", {"user": user}):
		return False
	# Check for owner-only / if-owner permission rule
	try:
		ptype_rules = frappe.permissions.get_role_permissions(doctype, user=user) or {}
		if ptype_rules.get("if_owner") and not ptype_rules.get("read"):
			return False
	except Exception:
		pass
	return True


def _require_unrestricted(doctype: str, tool_name: str):
	if not _user_has_unrestricted_access(doctype):
		raise PermissionError(
			f"You have row-level restrictions on {doctype}. The aggregate tool '{tool_name}' "
			"would leak rows you cannot see — please use a row-level tool instead."
		)


# ---------------------------------------------------------------------------
# Hard-coded safety rails
# ---------------------------------------------------------------------------
# Tool names matching any of these patterns are blocked at execution time.
# This is a belt-and-braces guard against the AI inventing or being tricked
# into calling a destructive tool that we never intended to expose.
_DESTRUCTIVE_TOOL_PATTERNS = (
	"delete",
	"remove",
	"drop",
	"purge",
	"trash",
	"cancel_doc",
	"cancel_document",
)

# Field names that the AI is NEVER allowed to set/update on any document.
# These are either security-sensitive or destructive when mis-set.
_FORBIDDEN_FIELDS = {
	"docstatus",          # 2 = cancelled, which is functionally a soft-delete
	"owner",
	"modified_by",
	"creation",
	"modified",
	"_user_tags",
	"_assign",
	"_seen",
	"_liked_by",
	"_comments",
	"name",               # Frappe will auto-name; AI shouldn't override
	"parent",             # only set internally for child rows
	"parenttype",
	"parentfield",
}


def _is_destructive_tool(name: str) -> bool:
	n = (name or "").lower()
	return any(pat in n for pat in _DESTRUCTIVE_TOOL_PATTERNS)


def _strip_forbidden_fields(values: dict) -> dict:
	"""Return a copy of values with forbidden keys removed. Used by every
	create/update tool so the AI can never set sensitive system fields."""
	if not isinstance(values, dict):
		return values
	clean = {k: v for k, v in values.items() if k not in _FORBIDDEN_FIELDS}
	# Reject explicit cancellation attempts encoded as a string
	for k in list(clean.keys()):
		if k.lower() == "docstatus":
			clean.pop(k, None)
	return clean


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


@dataclass
class Tool:
	name: str
	description: str
	parameters: dict
	handler: Callable[[dict, dict], Any]

	def schema(self) -> dict:
		return {
			"name": self.name,
			"description": self.description,
			"parameters": self.parameters,
		}


_TOOLS: dict[str, Tool] = {}


def register(tool: Tool):
	_TOOLS[tool.name] = tool


def all_tools() -> list[Tool]:
	return list(_TOOLS.values())


def get(name: str) -> Tool | None:
	return _TOOLS.get(name)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def _h_list_doctypes(args: dict, ctx: dict) -> dict:
	keyword = (args.get("keyword") or "").strip()
	limit = min(int(args.get("limit") or 50), 200)
	filters: dict = {"istable": 0}
	if keyword:
		filters["name"] = ["like", f"%{keyword}%"]
	# Use get_all here (DocType is metadata, not user data); we then filter the
	# list down to only those the *current user* can actually read.
	rows = frappe.get_all(
		"DocType",
		filters=filters,
		fields=["name", "module", "issingle", "is_submittable", "custom"],
		limit=limit,
		order_by="modified desc",
	)
	blocked = _settings().get_blocked_doctypes()
	visible = []
	for r in rows:
		if r.name in blocked:
			continue
		if r.name in {
			"User", "Role", "DocPerm", "Custom DocPerm", "Server Script", "Client Script",
			"OAuth Bearer Token", "OAuth Authorization Code", "OAuth Provider Settings",
			"Appe Buddy Settings", "Appe Buddy Tool Log", "System Settings", "Website Settings",
		}:
			continue
		try:
			if frappe.has_permission(r.name, ptype="read"):
				visible.append(r)
		except Exception:
			# DocType may have an exotic permission model; skip rather than leak
			continue
	return {"count": len(visible), "doctypes": visible}


def _h_get_doctype_meta(args: dict, ctx: dict) -> dict:
	doctype = args["doctype"]
	_ensure_doctype_allowed(doctype)
	_check_user_can("read", doctype)
	meta = frappe.get_meta(doctype)
	fields = []
	for f in meta.fields:
		fields.append(
			{
				"fieldname": f.fieldname,
				"label": f.label,
				"fieldtype": f.fieldtype,
				"options": f.options,
				"reqd": int(f.reqd or 0),
				"in_list_view": int(f.in_list_view or 0),
				"read_only": int(f.read_only or 0),
			}
		)
	return {
		"doctype": doctype,
		"module": meta.module,
		"issingle": meta.issingle,
		"istable": meta.istable,
		"is_submittable": meta.is_submittable,
		"autoname": meta.autoname,
		"fields": fields,
	}


def _h_query_data(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "query_data")
	doctype = args["doctype"]
	_ensure_doctype_allowed(doctype)
	_check_user_can("read", doctype)
	fields = args.get("fields") or ["name"]
	if not isinstance(fields, list) or not fields:
		fields = ["name"]
	filters = args.get("filters") or {}
	order_by = args.get("order_by") or "modified desc"
	max_rows = int(_settings().max_query_rows or 200)
	limit = min(int(args.get("limit") or 20), max_rows)

	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=fields,
		order_by=order_by,
		limit_page_length=limit,
	)
	return {"doctype": doctype, "count": len(rows), "rows": rows}


def _h_count_records(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "count_records")
	doctype = args["doctype"]
	_ensure_doctype_allowed(doctype)
	_check_user_can("read", doctype)
	filters = args.get("filters") or {}
	count = frappe.db.count(doctype, filters=filters)
	return {"doctype": doctype, "count": int(count or 0)}


# --- Create DocType --------------------------------------------------------


_ALLOWED_FIELDTYPES = {
	"Data",
	"Small Text",
	"Long Text",
	"Text",
	"Text Editor",
	"Markdown Editor",
	"HTML Editor",
	"Code",
	"Int",
	"Float",
	"Currency",
	"Percent",
	"Check",
	"Date",
	"Datetime",
	"Time",
	"Duration",
	"Select",
	"Link",
	"Dynamic Link",
	"Table",
	"Table MultiSelect",
	"Attach",
	"Attach Image",
	"Color",
	"Rating",
	"Phone",
	"Geolocation",
	"Section Break",
	"Column Break",
	"Tab Break",
	"Password",
	"Read Only",
	"JSON",
	"Signature",
	"Barcode",
}


def _h_create_doctype(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_create_doctype", "create_doctype")
	name = (args.get("name") or "").strip()
	if not name:
		raise ValueError("name is required")
	if frappe.db.exists("DocType", name):
		raise ValueError(f"DocType '{name}' already exists")
	module = args.get("module") or "Appe"
	if not frappe.db.exists("Module Def", module):
		module = "Appe"
	fields = args.get("fields") or []
	if not isinstance(fields, list) or not fields:
		raise ValueError("fields is required (non-empty list)")

	clean_fields = []
	for f in fields:
		fieldtype = (f.get("fieldtype") or "Data").strip()
		if fieldtype not in _ALLOWED_FIELDTYPES:
			raise ValueError(f"Disallowed fieldtype: {fieldtype}")
		fieldname = (f.get("fieldname") or "").strip()
		label = (f.get("label") or fieldname.replace("_", " ").title()).strip()
		if not fieldname:
			# auto from label
			fieldname = label.lower().replace(" ", "_")
		clean_fields.append(
			{
				"fieldname": fieldname,
				"label": label,
				"fieldtype": fieldtype,
				"options": f.get("options") or "",
				"reqd": 1 if f.get("reqd") else 0,
				"in_list_view": 1 if f.get("in_list_view") else 0,
				"read_only": 1 if f.get("read_only") else 0,
				"default": cstr(f.get("default") or ""),
				"description": f.get("description") or "",
			}
		)

	role = args.get("role") or "System Manager"
	doc = frappe.get_doc(
		{
			"doctype": "DocType",
			"name": name,
			"module": module,
			"custom": 1,
			"is_submittable": 1 if args.get("is_submittable") else 0,
			"track_changes": 1,
			"naming_rule": args.get("naming_rule") or "Random",
			"autoname": args.get("autoname") or "",
			"fields": clean_fields,
			"permissions": [
				{
					"role": role,
					"read": 1,
					"write": 1,
					"create": 1,
					"delete": 1,
					"report": 1,
					"export": 1,
					"share": 1,
					"print": 1,
					"email": 1,
				}
			],
		}
	)
	doc.insert(ignore_permissions=False)
	return {"name": doc.name, "module": doc.module, "fields": len(clean_fields)}


# --- Create Document -------------------------------------------------------


def _h_create_document(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "create_document")
	doctype = args["doctype"]
	_ensure_doctype_allowed(doctype)
	_check_user_can("create", doctype)
	values = args.get("values") or {}
	if not isinstance(values, dict):
		raise ValueError("values must be an object")
	# Strip system / sensitive fields the AI is never allowed to set.
	values = _strip_forbidden_fields(values)
	values["doctype"] = doctype
	doc = frappe.get_doc(values)
	doc.insert(ignore_permissions=False)
	# Defence in depth — even if some flow set docstatus implicitly, drop back
	# to draft. The AI is read+create+update only; submit/cancel must go via
	# the human user.
	if int(getattr(doc, "docstatus", 0) or 0) != 0:
		raise PermissionError("Appe Buddy may not submit/cancel documents — please do this yourself.")
	return {"doctype": doctype, "name": doc.name, "docstatus": 0}


def _h_update_document(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "update_document")
	doctype = args["doctype"]
	_ensure_doctype_allowed(doctype)
	_check_user_can("write", doctype)
	name = args["name"]
	values = args.get("values") or {}
	if not isinstance(values, dict):
		raise ValueError("values must be an object")
	values = _strip_forbidden_fields(values)
	doc = frappe.get_doc(doctype, name)
	# Hard-block updates on submitted/cancelled docs to prevent the AI from
	# bypassing Frappe's submit-locking via direct field writes.
	if int(getattr(doc, "docstatus", 0) or 0) != 0:
		raise PermissionError(
			f"{doctype} '{name}' is submitted/cancelled — Appe Buddy cannot modify locked documents."
		)
	for k, v in values.items():
		doc.set(k, v)
	doc.save(ignore_permissions=False)
	return {"doctype": doctype, "name": doc.name}


# --- Reports ----------------------------------------------------------------


def _h_list_reports(args: dict, ctx: dict) -> dict:
	keyword = (args.get("keyword") or "").strip()
	filters: dict = {"disabled": 0}
	if keyword:
		filters["name"] = ["like", f"%{keyword}%"]
	rows = frappe.get_all(
		"Report",
		filters=filters,
		fields=["name", "ref_doctype", "report_type", "is_standard", "module"],
		limit=int(args.get("limit") or 50),
		order_by="modified desc",
	)
	return {"count": len(rows), "reports": rows}


def _h_run_report(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_run_report", "run_report")
	from frappe.desk.query_report import run as run_query_report

	report = args["report"]
	filters = args.get("filters") or {}
	if not frappe.db.exists("Report", report):
		raise ValueError(f"Report '{report}' not found")
	ref_dt = frappe.db.get_value("Report", report, "ref_doctype")
	if ref_dt:
		_ensure_doctype_allowed(ref_dt)
		_check_user_can("read", ref_dt)
	result = run_query_report(report_name=report, filters=filters, user=frappe.session.user)
	columns = result.get("columns") or []
	rows = result.get("result") or []
	max_rows = int(_settings().max_query_rows or 200)
	return {
		"report": report,
		"columns": columns,
		"row_count": len(rows),
		"rows": rows[:max_rows],
		"truncated": len(rows) > max_rows,
	}


def _h_create_report(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_create_report", "create_report")
	name = (args.get("name") or "").strip()
	ref_doctype = (args.get("ref_doctype") or "").strip()
	if not name or not ref_doctype:
		raise ValueError("name and ref_doctype are required")
	_ensure_doctype_allowed(ref_doctype)
	_check_user_can("read", ref_doctype)
	if frappe.db.exists("Report", name):
		raise ValueError(f"Report '{name}' already exists")

	report_type = args.get("report_type") or "Report Builder"
	if report_type not in ("Report Builder", "Query Report"):
		raise ValueError("report_type must be 'Report Builder' or 'Query Report'")

	doc = frappe.get_doc(
		{
			"doctype": "Report",
			"report_name": name,
			"ref_doctype": ref_doctype,
			"is_standard": "No",
			"report_type": report_type,
			"query": args.get("query") or "",
			"json": json.dumps(
				{
					"filters": args.get("filters") or [],
					"columns": args.get("columns") or [],
					"sort_by": args.get("sort_by") or "modified",
					"sort_order": args.get("sort_order") or "desc",
				}
			)
			if report_type == "Report Builder"
			else None,
		}
	)
	doc.insert(ignore_permissions=False)
	return {"name": doc.name, "ref_doctype": doc.ref_doctype, "report_type": doc.report_type}


# --- Dashboard Chart --------------------------------------------------------


def _h_create_dashboard_chart(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_create_chart", "create_dashboard_chart")
	name = (args.get("name") or "").strip()
	doctype = (args.get("doctype") or "").strip()
	if not name or not doctype:
		raise ValueError("name and doctype are required")
	_ensure_doctype_allowed(doctype)
	_check_user_can("read", doctype)
	if frappe.db.exists("Dashboard Chart", name):
		raise ValueError(f"Dashboard Chart '{name}' already exists")
	chart_type = args.get("chart_type") or "Count"  # Count / Sum / Average / Group By
	timespan = args.get("timespan") or "Last Year"
	time_interval = args.get("time_interval") or "Monthly"
	chart_doc_type = args.get("chart_doc_type") or "Line"
	based_on = args.get("based_on") or "creation"
	value_based_on = args.get("value_based_on")
	group_by_based_on = args.get("group_by_based_on")
	filters_json = args.get("filters_json") or "{}"
	if not isinstance(filters_json, str):
		filters_json = json.dumps(filters_json)

	doc = frappe.get_doc(
		{
			"doctype": "Dashboard Chart",
			"chart_name": name,
			"chart_type": chart_type,
			"document_type": doctype,
			"based_on": based_on if chart_type in ("Count", "Sum", "Average") else None,
			"value_based_on": value_based_on if chart_type in ("Sum", "Average") else None,
			"group_by_based_on": group_by_based_on if chart_type == "Group By" else None,
			"group_by_type": args.get("group_by_type") or "Count",
			"timespan": timespan,
			"time_interval": time_interval,
			"type": chart_doc_type,
			"filters_json": filters_json,
			"is_public": 1 if args.get("is_public") else 0,
			"timeseries": 1 if chart_type != "Group By" else 0,
		}
	)
	doc.insert(ignore_permissions=False)
	return {"name": doc.name, "doctype": doctype, "chart_type": chart_type}


# --- Number Card ------------------------------------------------------------


def _h_create_number_card(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_create_number_card", "create_number_card")
	name = (args.get("name") or "").strip()
	doctype = (args.get("doctype") or "").strip()
	if not name or not doctype:
		raise ValueError("name and doctype are required")
	_ensure_doctype_allowed(doctype)
	_check_user_can("read", doctype)
	if frappe.db.exists("Number Card", name):
		raise ValueError(f"Number Card '{name}' already exists")
	function = args.get("function") or "Count"
	if function not in ("Count", "Sum", "Average", "Min", "Max"):
		raise ValueError("function must be Count/Sum/Average/Min/Max")
	filters_json = args.get("filters_json") or "[]"
	if not isinstance(filters_json, str):
		filters_json = json.dumps(filters_json)
	doc = frappe.get_doc(
		{
			"doctype": "Number Card",
			"label": name,
			"document_type": doctype,
			"function": function,
			"aggregate_function_based_on": args.get("aggregate_function_based_on"),
			"filters_json": filters_json,
			"is_public": 1 if args.get("is_public") else 0,
		}
	)
	doc.insert(ignore_permissions=False)
	return {"name": doc.name, "function": function}


# --- Dashboard --------------------------------------------------------------


def _h_create_dashboard(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_create_dashboard", "create_dashboard")
	name = (args.get("name") or "").strip()
	if not name:
		raise ValueError("name is required")
	if frappe.db.exists("Dashboard", name):
		raise ValueError(f"Dashboard '{name}' already exists")

	charts = args.get("charts") or []
	cards = args.get("number_cards") or []
	dash = frappe.get_doc(
		{
			"doctype": "Dashboard",
			"dashboard_name": name,
			"is_default": 0,
			"is_standard": 0,
			"module": args.get("module") or "Appe",
			"charts": [{"chart": c, "width": "Half"} for c in charts if frappe.db.exists("Dashboard Chart", c)],
			"cards": [{"card": c} for c in cards if frappe.db.exists("Number Card", c)],
		}
	)
	dash.insert(ignore_permissions=False)
	return {
		"name": dash.name,
		"charts_added": len(dash.charts),
		"cards_added": len(dash.cards),
	}


# --- Misc helpers -----------------------------------------------------------


def _h_get_current_user(args: dict, ctx: dict) -> dict:
	user = frappe.session.user
	roles = frappe.get_roles(user)
	full_name = frappe.db.get_value("User", user, "full_name")
	return {"user": user, "full_name": full_name, "roles": roles}


# ---------------------------------------------------------------------------
# Register all tools
# ---------------------------------------------------------------------------


def _register_all():
	register(
		Tool(
			name="get_current_user",
			description="Return the currently logged-in user, their full name and roles.",
			parameters={"type": "object", "properties": {}},
			handler=_h_get_current_user,
		)
	)
	register(
		Tool(
			name="list_doctypes",
			description="List DocTypes available in the system. Optionally filter by keyword in name.",
			parameters={
				"type": "object",
				"properties": {
					"keyword": {"type": "string", "description": "Substring filter on DocType name."},
					"limit": {"type": "integer", "default": 50},
				},
			},
			handler=_h_list_doctypes,
		)
	)
	register(
		Tool(
			name="get_doctype_meta",
			description="Fetch fields and metadata for a given DocType.",
			parameters={
				"type": "object",
				"properties": {"doctype": {"type": "string"}},
				"required": ["doctype"],
			},
			handler=_h_get_doctype_meta,
		)
	)
	register(
		Tool(
			name="query_data",
			description=(
				"Query records from a DocType. Use this to read business data. "
				"Returns rows with the requested fields. Respect user permissions."
			),
			parameters={
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"fields": {"type": "array", "items": {"type": "string"}, "default": ["name"]},
					"filters": {"type": "object", "description": "Frappe filter dict, e.g. {\"status\": \"Open\"}"},
					"order_by": {"type": "string", "default": "modified desc"},
					"limit": {"type": "integer", "default": 20},
				},
				"required": ["doctype"],
			},
			handler=_h_query_data,
		)
	)
	register(
		Tool(
			name="count_records",
			description="Return the count of records matching the given filters for a DocType.",
			parameters={
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"filters": {"type": "object"},
				},
				"required": ["doctype"],
			},
			handler=_h_count_records,
		)
	)
	register(
		Tool(
			name="create_document",
			description="Create a new document of any DocType the user has create permission for.",
			parameters={
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"values": {"type": "object", "description": "Field values for the new document"},
				},
				"required": ["doctype", "values"],
			},
			handler=_h_create_document,
		)
	)
	register(
		Tool(
			name="update_document",
			description="Update an existing document.",
			parameters={
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"name": {"type": "string"},
					"values": {"type": "object"},
				},
				"required": ["doctype", "name", "values"],
			},
			handler=_h_update_document,
		)
	)
	register(
		Tool(
			name="create_doctype",
			description=(
				"Create a brand new custom DocType. Use this when the user asks for a new table / module / entity. "
				"Fields is a list of {fieldname, label, fieldtype, options?, reqd?, in_list_view?, default?, description?}."
			),
			parameters={
				"type": "object",
				"properties": {
					"name": {"type": "string"},
					"module": {"type": "string", "default": "Appe"},
					"is_submittable": {"type": "boolean", "default": False},
					"naming_rule": {"type": "string", "description": "e.g. 'Random', 'By fieldname', 'Expression'"},
					"autoname": {"type": "string"},
					"role": {"type": "string", "default": "System Manager"},
					"fields": {
						"type": "array",
						"items": {
							"type": "object",
							"properties": {
								"fieldname": {"type": "string"},
								"label": {"type": "string"},
								"fieldtype": {"type": "string"},
								"options": {"type": "string"},
								"reqd": {"type": "boolean"},
								"in_list_view": {"type": "boolean"},
								"default": {"type": "string"},
								"description": {"type": "string"},
							},
							"required": ["fieldtype"],
						},
					},
				},
				"required": ["name", "fields"],
			},
			handler=_h_create_doctype,
		)
	)
	register(
		Tool(
			name="list_reports",
			description="List existing Frappe Reports.",
			parameters={
				"type": "object",
				"properties": {
					"keyword": {"type": "string"},
					"limit": {"type": "integer", "default": 50},
				},
			},
			handler=_h_list_reports,
		)
	)
	register(
		Tool(
			name="run_report",
			description="Run an existing Frappe Report and return rows.",
			parameters={
				"type": "object",
				"properties": {
					"report": {"type": "string"},
					"filters": {"type": "object"},
				},
				"required": ["report"],
			},
			handler=_h_run_report,
		)
	)
	register(
		Tool(
			name="create_report",
			description=(
				"Create a new custom Report (Report Builder or Query Report). "
				"For Report Builder pass `columns`, `filters`, `sort_by`, `sort_order`. "
				"For Query Report pass `query` (SQL)."
			),
			parameters={
				"type": "object",
				"properties": {
					"name": {"type": "string"},
					"ref_doctype": {"type": "string"},
					"report_type": {"type": "string", "enum": ["Report Builder", "Query Report"]},
					"query": {"type": "string"},
					"columns": {
						"type": "array",
						"items": {"type": "object", "additionalProperties": True},
					},
					"filters": {
						"type": "array",
						"items": {"type": "object", "additionalProperties": True},
					},
					"sort_by": {"type": "string"},
					"sort_order": {"type": "string"},
				},
				"required": ["name", "ref_doctype"],
			},
			handler=_h_create_report,
		)
	)
	register(
		Tool(
			name="create_dashboard_chart",
			description="Create a Dashboard Chart (line/bar/donut/pie/percent).",
			parameters={
				"type": "object",
				"properties": {
					"name": {"type": "string"},
					"doctype": {"type": "string"},
					"chart_type": {
						"type": "string",
						"enum": ["Count", "Sum", "Average", "Group By"],
						"default": "Count",
					},
					"chart_doc_type": {
						"type": "string",
						"enum": ["Line", "Bar", "Donut", "Pie", "Percentage", "Heatmap"],
						"default": "Line",
					},
					"timespan": {"type": "string", "default": "Last Year"},
					"time_interval": {"type": "string", "default": "Monthly"},
					"based_on": {"type": "string", "default": "creation"},
					"value_based_on": {"type": "string"},
					"group_by_based_on": {"type": "string"},
					"group_by_type": {"type": "string"},
					"filters_json": {"type": "string"},
					"is_public": {"type": "boolean", "default": True},
				},
				"required": ["name", "doctype"],
			},
			handler=_h_create_dashboard_chart,
		)
	)
	register(
		Tool(
			name="create_number_card",
			description="Create a Number Card (KPI tile).",
			parameters={
				"type": "object",
				"properties": {
					"name": {"type": "string"},
					"doctype": {"type": "string"},
					"function": {"type": "string", "enum": ["Count", "Sum", "Average", "Min", "Max"]},
					"aggregate_function_based_on": {"type": "string"},
					"filters_json": {"type": "string"},
					"is_public": {"type": "boolean", "default": True},
				},
				"required": ["name", "doctype"],
			},
			handler=_h_create_number_card,
		)
	)
	register(
		Tool(
			name="create_dashboard",
			description="Create a Dashboard combining existing Dashboard Charts and Number Cards.",
			parameters={
				"type": "object",
				"properties": {
					"name": {"type": "string"},
					"module": {"type": "string", "default": "Appe"},
					"charts": {"type": "array", "items": {"type": "string"}},
					"number_cards": {"type": "array", "items": {"type": "string"}},
				},
				"required": ["name"],
			},
			handler=_h_create_dashboard,
		)
	)


_register_all()


# Side-effect import: registers ERPNext-specific tools (no-op if ERPNext is not installed).
try:
	from . import erpnext_tools as _erpnext_tools  # noqa: F401
except Exception:
	frappe.log_error(message=frappe.get_traceback(), title="Appe Buddy: erpnext_tools load failed")


# ---------------------------------------------------------------------------
# Execution wrapper
# ---------------------------------------------------------------------------


def execute_tool(name: str, arguments: dict, *, conversation: str | None = None) -> dict:
	"""Execute a registered tool. Returns a JSON-safe dict.

	Always logs to 'Appe Buddy Tool Log'. Never raises; instead returns
	{"ok": False, "error": "..."} on failure so the LLM can recover.
	"""
	started = time.time()

	# Hard block: AI is NEVER allowed to call destructive tools, even if a
	# malicious prompt convinces it to invent one. This catches `delete_*`,
	# `remove_*`, `drop_*`, `purge_*`, `cancel_doc*` etc.
	if _is_destructive_tool(name):
		_log_tool(name, arguments, None, "Blocked", "Destructive tool blocked", 0, conversation)
		return {
			"ok": False,
			"error": (
				f"Destructive operation '{name}' is blocked by Appe Buddy policy. "
				"Records are never deleted by the AI — please ask a human admin."
			),
		}

	tool = get(name)
	if not tool:
		_log_tool(name, arguments, None, "Error", "Unknown tool", 0, conversation)
		return {"ok": False, "error": f"Unknown tool: {name}"}

	try:
		result = tool.handler(arguments or {}, {"conversation": conversation}) or {}
		duration_ms = int((time.time() - started) * 1000)
		_log_tool(name, arguments, result, "Success", None, duration_ms, conversation)
		return {"ok": True, "result": result}
	except PermissionError as e:
		duration_ms = int((time.time() - started) * 1000)
		_log_tool(name, arguments, None, "Blocked", str(e), duration_ms, conversation)
		return {"ok": False, "error": f"Permission denied: {e}"}
	except Exception as e:
		duration_ms = int((time.time() - started) * 1000)
		frappe.log_error(message=frappe.get_traceback(), title=f"Appe Buddy tool '{name}' failed")
		_log_tool(name, arguments, None, "Error", str(e), duration_ms, conversation)
		return {"ok": False, "error": str(e)}


def _log_tool(name, arguments, result, status, error, duration_ms, conversation):
	try:
		doc = frappe.get_doc(
			{
				"doctype": "Appe Buddy Tool Log",
				"tool_name": name,
				"user": frappe.session.user,
				"conversation": conversation,
				"status": status,
				"duration_ms": duration_ms,
				"arguments": json.dumps(arguments or {}, default=str)[:65000],
				"result": (json.dumps(result, default=str)[:65000] if result is not None else None),
				"error": (error or "")[:65000] or None,
			}
		)
		doc.insert(ignore_permissions=True)
	except Exception:
		# Never fail the request just because logging failed
		frappe.log_error(message=frappe.get_traceback(), title="Appe Buddy tool log insert failed")


def tool_schemas() -> list[dict]:
	"""All tool schemas (OpenAI-style) honoring capability flags."""
	s = _settings()
	allowed = []
	for t in all_tools():
		# Hide tools whose capability is disabled
		if t.name in ("create_doctype",) and not s.allow_create_doctype:
			continue
		if t.name in ("create_report",) and not s.allow_create_report:
			continue
		if t.name in ("create_dashboard_chart",) and not s.allow_create_chart:
			continue
		if t.name in ("create_dashboard",) and not s.allow_create_dashboard:
			continue
		if t.name in ("create_number_card",) and not s.allow_create_number_card:
			continue
		if t.name in ("run_report",) and not s.allow_run_report:
			continue
		if t.name in ("query_data", "count_records", "create_document", "update_document") and not s.allow_query_data:
			continue
		allowed.append(t.schema())
	return allowed
