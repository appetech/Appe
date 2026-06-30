from __future__ import annotations

import re

import frappe

from .ecosystem_kb import (
	FRAPPE_APPS,
	ERPNEXT_MODULE_DOCS,
	erpnext_doctype_doc_url,
	frappe_doctype_doc_url,
	github_source_path,
)
from .tools import Tool, _check_user_can, _ensure_capability, register


def _ensure_docs_read(tool_name: str):
	_ensure_capability("allow_query_data", tool_name)


def _app_for_doctype(doctype: str) -> tuple[str, str | None]:
	"""Return (app_name, module) for a DocType."""
	if not frappe.db.exists("DocType", doctype):
		return "", None
	module = frappe.db.get_value("DocType", doctype, "module")
	if not module:
		return "frappe", None
	# Map module to app via Module Def
	app = frappe.db.get_value("Module Def", module, "app_name") or "frappe"
	return app, module


def _desk_url(doctype: str, docname: str | None = None) -> str:
	base = frappe.utils.get_url()
	if docname:
		return f"{base}/app/{frappe.scrub(doctype)}/{docname}"
	return f"{base}/app/{frappe.scrub(doctype)}"


def _search_topics(query: str, limit: int = 15) -> list[dict]:
	"""Search curated topic links across all known apps."""
	q = query.lower().strip()
	if not q:
		return []
	tokens = [t for t in re.split(r"[\s,/]+", q) if t]
	results: list[dict] = []
	seen: set[str] = set()

	def _add(item: dict):
		key = item.get("url") or item.get("title")
		if key and key not in seen:
			seen.add(key)
			results.append(item)

	for app_key, info in FRAPPE_APPS.items():
		for label, url in info.get("key_topics", []):
			hay = f"{label} {url}".lower()
			if q in hay or all(t in hay for t in tokens):
				_add({"app": app_key, "title": label, "url": url, "type": "topic"})
		for mod, url in info.get("modules", {}).items():
			hay = f"{mod} {url}".lower()
			if q in hay or all(t in hay for t in tokens):
				_add({"app": app_key, "title": f"{mod} module", "url": url, "type": "module"})
		title_hay = f"{info.get('title','')} {app_key} {info.get('summary','')}".lower()
		if q in title_hay or all(t in title_hay for t in tokens):
			if info.get("docs"):
				_add({"app": app_key, "title": info["title"], "url": info["docs"], "type": "app_docs"})
			if info.get("github"):
				_add({"app": app_key, "title": f"{info['title']} GitHub", "url": info["github"], "type": "github"})
	# Also search local DocTypes the user can read
	try:
		dts = frappe.get_all(
			"DocType",
			filters={"name": ["like", f"%{query}%"], "istable": 0},
			fields=["name", "module"],
			limit=10,
		)
		for dt in dts:
			try:
				if frappe.has_permission(dt.name, "read"):
					app, _ = _app_for_doctype(dt.name)
					_add(
						{
							"app": app,
							"title": dt.name,
							"url": erpnext_doctype_doc_url(dt.name) if app == "erpnext" else frappe_doctype_doc_url(dt.name),
							"type": "doctype_doc",
							"desk": _desk_url(dt.name),
						}
					)
			except Exception:
				continue
	except Exception:
		pass
	return results[:limit]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _h_list_frappe_ecosystem_apps(args: dict, ctx: dict) -> dict:
	_ensure_docs_read("list_frappe_ecosystem_apps")
	installed = set(frappe.get_installed_apps() or [])
	apps_out = []
	for key, info in FRAPPE_APPS.items():
		apps_out.append(
			{
				"app": key,
				"title": info.get("title") or key,
				"installed": key in installed,
				"summary": info.get("summary"),
				"docs": info.get("docs"),
				"github": info.get("github"),
				"docs_user_manual": info.get("docs_user_manual"),
			}
		)
	# Include installed apps not in registry
	for key in installed:
		if key not in FRAPPE_APPS:
			apps_out.append({"app": key, "title": key, "installed": True, "summary": "Custom/unknown app"})
	return {"count": len(apps_out), "installed_count": len(installed), "apps": apps_out}


def _h_get_app_documentation(args: dict, ctx: dict) -> dict:
	_ensure_docs_read("get_app_documentation")
	app = (args.get("app") or "").strip().lower()
	topic = (args.get("topic") or "").strip().lower()
	if not app:
		raise ValueError("app is required (e.g. erpnext, frappe, hrms, india_compliance, education)")
	info = FRAPPE_APPS.get(app)
	if not info:
		installed = frappe.get_installed_apps() or []
		if app in installed:
			return {
				"app": app,
				"installed": True,
				"note": f"App '{app}' is installed but not in the curated registry. Check /apps/{app} locally.",
			}
		raise ValueError(f"Unknown app '{app}'. Call list_frappe_ecosystem_apps for known apps.")

	out: dict = {
		"app": app,
		"title": info.get("title"),
		"installed": app in (frappe.get_installed_apps() or []),
		"summary": info.get("summary"),
		"docs": info.get("docs"),
		"docs_user_manual": info.get("docs_user_manual"),
		"github": info.get("github"),
		"forum": info.get("forum"),
		"key_topics": [{"title": t, "url": u} for t, u in info.get("key_topics", [])],
	}
	if info.get("modules"):
		out["modules"] = [{"name": k, "url": v} for k, v in info["modules"].items()]
	if topic and info.get("modules"):
		for mod, url in info["modules"].items():
			if topic in mod.lower():
				out["matched_module"] = {"name": mod, "url": url}
				break
	if topic and not out.get("matched_module"):
		for t, u in info.get("key_topics", []):
			if topic in t.lower() or topic in u.lower():
				out["matched_topic"] = {"title": t, "url": u}
				break
	return out


def _h_get_doctype_resources(args: dict, ctx: dict) -> dict:
	_ensure_docs_read("get_doctype_resources")
	doctype = (args.get("doctype") or "").strip()
	if not doctype:
		raise ValueError("doctype is required")
	if not frappe.db.exists("DocType", doctype):
		raise ValueError(f"DocType '{doctype}' not found on this site")

	_check_user_can("read", doctype)
	app, module = _app_for_doctype(doctype)
	meta = frappe.get_meta(doctype)

	# Official doc URL (best-effort)
	if app == "erpnext":
		official_doc = erpnext_doctype_doc_url(doctype)
	elif app in ("hrms",):
		slug = doctype.lower().replace(" ", "-")
		official_doc = f"https://docs.frappe.io/hr/en/{slug}"
	elif app == "india_compliance":
		slug = doctype.lower().replace(" ", "-")
		official_doc = f"https://docs.indiacompliance.app/docs/{slug}"
	else:
		official_doc = frappe_doctype_doc_url(doctype)

	github = github_source_path(app, doctype, module)
	module_doc = None
	if app == "erpnext" and module and module in ERPNEXT_MODULE_DOCS:
		module_doc = f"https://docs.erpnext.com/docs/user/manual/en/{ERPNEXT_MODULE_DOCS[module]}"

	fields_summary = [
		{
			"fieldname": f.fieldname,
			"label": f.label,
			"fieldtype": f.fieldtype,
			"reqd": int(f.reqd or 0),
			"options": f.options or None,
		}
		for f in meta.fields[:40]
	]

	return {
		"doctype": doctype,
		"app": app,
		"module": module,
		"issingle": meta.issingle,
		"is_submittable": meta.is_submittable,
		"istable": meta.istable,
		"is_tree": getattr(meta, "is_tree", 0),
		"autoname": meta.autoname,
		"desk_list_url": _desk_url(doctype),
		"official_documentation": official_doc,
		"module_documentation": module_doc,
		"github_source": github,
		"fields_preview": fields_summary,
		"fields_total": len(meta.fields),
		"note": (
			"Share official_documentation and github_source links with the user. "
			"For full field list use get_doctype_meta tool."
		),
	}


def _h_search_official_docs(args: dict, ctx: dict) -> dict:
	_ensure_docs_read("search_official_docs")
	query = (args.get("query") or args.get("q") or "").strip()
	if not query:
		raise ValueError("query is required")
	limit = min(int(args.get("limit") or 15), 25)
	results = _search_topics(query, limit=limit)
	return {
		"query": query,
		"count": len(results),
		"results": results,
		"note": "These are curated official doc links. Open the URL for the full guide.",
	}


def _h_get_frappe_api_reference(args: dict, ctx: dict) -> dict:
	"""Quick reference for common Frappe/ERPNext API patterns."""
	_ensure_docs_read("get_frappe_api_reference")
	topic = (args.get("topic") or "rest").strip().lower()
	references = {
		"rest": {
			"title": "Frappe REST API",
			"url": "https://docs.frappe.io/framework/user/en/api/rest",
			"examples": [
				"GET /api/resource/{DocType}?fields=[\"name\",\"status\"]&filters=[[\"status\",\"=\",\"Open\"]]",
				"GET /api/resource/{DocType}/{name}",
				"POST /api/resource/{DocType}  (JSON body)",
				"PUT /api/resource/{DocType}/{name}",
				"POST /api/method/{dotted.path}  (RPC)",
				"Auth: Authorization: token {api_key}:{api_secret}",
			],
		},
		"appe_buddy": {
			"title": "Appe Buddy Mobile API",
			"url": "/appe/ai/README.md",
			"examples": [
				"GET /api/method/appe.ai.api.me",
				"POST /api/method/appe.ai.api.send_message",
				"GET /api/method/appe.ai.api.list_conversations",
				"GET /api/method/appe.appe_api.get_module_data",
				"GET /api/method/appe.appe_api.get_dashboard_sections",
			],
		},
		"erpnext_api": {
			"title": "ERPNext API",
			"url": "https://docs.frappe.io/erpnext/user/en/api",
			"examples": [
				"Same REST API as Frappe — all DocTypes exposed at /api/resource/",
				"Reports: POST /api/method/frappe.desk.query_report.run",
			],
		},
		"hooks": {
			"title": "Frappe Hooks",
			"url": "https://docs.frappe.io/framework/user/en/python-hooks",
			"examples": ["hooks.py in each app — doc_events, scheduler_events, override_whitelisted_methods"],
		},
		"report": {
			"title": "Script / Query Reports",
			"url": "https://docs.frappe.io/framework/user/en/desk/reports",
			"examples": [
				"Script Report: Python file in app/{module}/report/{name}/{name}.py",
				"Query Report: SQL in Report doctype",
				"Report Builder: JSON config in Report doctype",
			],
		},
	}
	ref = references.get(topic)
	if not ref:
		return {"topic": topic, "available_topics": list(references.keys()), "references": references}
	return {"topic": topic, **ref}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_docs_tools():
	register(
		Tool(
			name="list_frappe_ecosystem_apps",
			description=(
				"List all known Frappe ecosystem apps (ERPNext, HRMS, India Compliance, Education, etc.) "
				"with official docs URLs, GitHub repos, and whether each is installed on THIS site."
			),
			parameters={"type": "object", "properties": {}},
			handler=_h_list_frappe_ecosystem_apps,
		)
	)
	register(
		Tool(
			name="get_app_documentation",
			description=(
				"Get official documentation links, GitHub repo, module docs, and key topics for a Frappe app. "
				"Apps: frappe, erpnext, hrms, india_compliance, education, lms, helpdesk, payments, etc."
			),
			parameters={
				"type": "object",
				"properties": {
					"app": {"type": "string", "description": "App name e.g. erpnext, hrms, frappe"},
					"topic": {"type": "string", "description": "Optional module/topic filter e.g. stock, payroll, gst"},
				},
				"required": ["app"],
			},
			handler=_h_get_app_documentation,
		)
	)
	register(
		Tool(
			name="get_doctype_resources",
			description=(
				"For any DocType: return official ERPNext/Frappe documentation URL, GitHub source path, "
				"desk link, module info, and field preview. Use when user asks how a DocType works or wants docs."
			),
			parameters={
				"type": "object",
				"properties": {"doctype": {"type": "string"}},
				"required": ["doctype"],
			},
			handler=_h_get_doctype_resources,
		)
	)
	register(
		Tool(
			name="search_official_docs",
			description=(
				"Search official Frappe/ERPNext/HRMS documentation links by keyword. "
				"Returns curated doc URLs — share these with the user for the full guide."
			),
			parameters={
				"type": "object",
				"properties": {
					"query": {"type": "string"},
					"limit": {"type": "integer", "default": 15},
				},
				"required": ["query"],
			},
			handler=_h_search_official_docs,
		)
	)
	register(
		Tool(
			name="get_frappe_api_reference",
			description=(
				"Quick API reference with official doc links and example endpoints. "
				"Topics: rest, erpnext_api, appe_buddy, hooks, report."
			),
			parameters={
				"type": "object",
				"properties": {
					"topic": {
						"type": "string",
						"enum": ["rest", "erpnext_api", "appe_buddy", "hooks", "report"],
						"default": "rest",
					},
				},
			},
			handler=_h_get_frappe_api_reference,
		)
	)


register_docs_tools()
