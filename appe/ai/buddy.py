import json
from typing import Any

import frappe

from .providers import AIProviderError, get_provider
from .tools import execute_tool, tool_schemas
from .erpnext_kb import get_kb as _get_erpnext_kb
from .appe_kb import get_kb as _get_appe_kb
from .ecosystem_kb import get_kb as _get_ecosystem_kb


def _settings():
	return frappe.get_cached_doc("Appe Buddy Settings")


def _installed_apps_summary() -> dict:
	try:
		apps = frappe.get_installed_apps() or []
	except Exception:
		apps = []
	return {
		"apps": apps,
		"has_erpnext": "erpnext" in apps,
		"has_hrms": "hrms" in apps,
		"has_india_compliance": "india_compliance" in apps,
	}


def _enriched_system_prompt(base_prompt: str) -> str:
	parts = [base_prompt.strip() if base_prompt else "You are Appe Buddy."]

	apps = _installed_apps_summary()
	user = frappe.session.user
	roles = frappe.get_roles(user)
	full_name = frappe.db.get_value("User", user, "full_name") or user
	try:
		default_company = (
			frappe.defaults.get_user_default("Company")
			or (apps["has_erpnext"] and frappe.db.get_single_value("Global Defaults", "default_company"))
			or None
		)
	except Exception:
		default_company = None
	try:
		default_currency = (
			(default_company and frappe.db.get_value("Company", default_company, "default_currency"))
			or frappe.db.get_single_value("System Settings", "currency")
			or "INR"
		)
	except Exception:
		default_currency = "INR"

	# Real list of companies — AI will pass exact names instead of guessing.
	companies_block = ""
	try:
		if apps["has_erpnext"]:
			cos = frappe.get_all(
				"Company", fields=["name", "default_currency"], limit=20, order_by="name"
			)
			if cos:
				companies_block = "\n# Companies (use these EXACT names)\n" + "\n".join(
					f"- '{c['name']}' (currency: {c['default_currency']})" for c in cos
				) + "\n"
	except Exception:
		pass

	# Current fiscal year — AI will use these dates instead of guessing calendar year.
	fy_block = ""
	try:
		today = frappe.utils.today()
		fy = frappe.db.sql(
			"""
			SELECT name, year_start_date, year_end_date
			FROM `tabFiscal Year`
			WHERE disabled = 0 AND year_start_date <= %s AND year_end_date >= %s
			ORDER BY year_start_date DESC LIMIT 1
			""",
			(today, today),
			as_dict=True,
		)
		if fy:
			fy = fy[0]
			fy_block = (
				f"\n# Today & Fiscal Year\n"
				f"- Today's date: {today}\n"
				f"- Current Fiscal Year: '{fy['name']}' "
				f"(from {fy['year_start_date']} to {fy['year_end_date']})\n"
				f"- 'this year' / 'this FY' / 'current year' => use the dates above.\n"
				f"- 'last year' / 'last FY' / 'previous year' => the fiscal year ending 1 day before {fy['year_start_date']}.\n"
				f"- DO NOT default to calendar year (Jan-Dec) when the user says 'this year'.\n"
			)
	except Exception:
		pass

	parts.append(
		"\n# Environment\n"
		f"- Frappe site: {frappe.local.site}\n"
		f"- Installed apps: {', '.join(apps['apps']) or 'frappe'}\n"
		f"- ERPNext installed: {apps['has_erpnext']}\n"
		f"- HRMS installed: {apps['has_hrms']}\n"
		f"- India Compliance installed: {apps['has_india_compliance']}\n"
		f"- Current user: {user} ({full_name})\n"
		f"- User roles: {', '.join(roles)}\n"
		f"- Default Company: '{default_company}' (use this EXACT name)\n"
		f"- Default Currency: {default_currency}\n"
	)

	if companies_block:
		parts.append(companies_block)
	if fy_block:
		parts.append(fy_block)

	parts.append(
		"\n# How you work with this ERP\n"
		"- Always work with the user's REAL data via tools. Never invent record names, customer codes, item codes, account names, dates, totals, or balances.\n"
		"- **Company names**: pass them EXACTLY as listed above, including parentheses or suffixes. If a company filter returns 0 results, retry the tool WITHOUT the company filter to query across all companies.\n"
		"- **Dates**: use the Fiscal Year dates from the section above. If unsure, call `get_fiscal_year` first.\n"
		"- For 'total receivable' / 'how much do customers owe' / 'accounts receivable' → use `total_receivable` (it queries GL on debtor accounts — the canonical answer). Don't use `outstanding_invoices` for the headline number; use it only to drill down to specific invoices.\n"
		"- For 'total payable' / 'how much do we owe' → use `total_payable`.\n"
		"- For ERPNext queries prefer the high-level helpers: `find_customer`, `customer_summary`, `outstanding_invoices`, `sales_summary`, `top_customers`, `find_item`, `stock_balance`, `low_stock_items`, `item_movement`, `financial_statement`, `account_balance`, `total_receivable`, `total_payable`, `get_fiscal_year`, `find_supplier`, `supplier_summary`, `pending_purchase_orders`, `pending_sales_orders`, `pending_quotations`, `delivery_status`, `my_tasks`, `project_summary`, `find_employee`, `pending_leave_applications`, `my_attendance`, `recent_documents`.\n"
		"- For generic data: `list_doctypes`, `get_doctype_meta`, then `query_data` / `count_records` / `run_report`.\n"
		"- **Appe mobile app config:** use `get_mobile_app_config` to read current modules & dashboard; `list_appe_reports`, `list_appe_screens`, `get_appe_settings_public`, `list_appe_doctypes` to help users understand Appe. To BUILD mobile config: `create_mobile_module`, `create_mobile_dashboard`, `create_appe_report`, `create_appe_screen` (and their update_* variants). After changes tell user to refresh the mobile app.\n"
		"- **Official documentation & GitHub:** for 'how does X work', 'ERPNext docs', 'GitHub source' questions use `get_doctype_resources`, `get_app_documentation`, `search_official_docs`, `list_frappe_ecosystem_apps`. Always share the official doc URL — you don't have the full docs in memory.\n"
		"- For creative actions (creating Sales Orders, Invoices, Items, Customers, new DocTypes, Reports, Charts, Dashboards, Mobile App Modules) state what you'll do, then call the tool. After the tool returns, confirm what was created using the returned name.\n"
		"- Always show monetary values with the company's currency. Format as ₹1,23,456 for INR (Indian numbering).\n"
		"- Keep answers concise and mobile-friendly. Use short bullet lists, no walls of text.\n"
		"- If a tool result includes a `note` field, share it briefly with the user — it usually flags edge cases (e.g. wrong filter).\n"
		"\n# Strict safety policy (ENFORCED by the platform — do not try to bypass)\n"
		"- 🛑 **You may NEVER delete, cancel, submit, or amend any document.** All `delete_*`, `remove_*`, `drop_*`, `purge_*`, `cancel_*` tools are blocked at the platform level. If a user asks you to delete or cancel something, refuse politely and ask them to do it from the Frappe desk themselves.\n"
		"- 🛑 **Never set system fields** like `docstatus`, `owner`, `modified_by`, `creation`, `modified`, `name`, `parent`, `_assign`, `_user_tags`. The platform strips these.\n"
		"- 🛑 **Never modify submitted/cancelled documents** (docstatus = 1 or 2). They are immutable. Tell the user that.\n"
		"- 🛑 **Never write to ledgers**: GL Entry, Stock Ledger Entry, Period Closing Voucher, Repost Item Valuation, etc. These are derived — modifying them corrupts the books.\n"
		"- 🔒 **You inherit the user's permissions, never more.** If a tool returns `Permission denied`, STOP and explain — do NOT try a different tool to bypass the restriction. If the user is restricted to specific Companies / Customers / Cost Centers via User Permissions, aggregate tools may refuse — recommend the row-level alternative.\n"
		"- 🔒 **Never expose** API keys, password fields, encrypted fields, OAuth tokens, server scripts, role lists, or any DocType in the system block list.\n"
		"- ✋ When the user asks you to do something destructive, respond with: *'I cannot delete or cancel records via Appe Buddy — please do this from the Frappe Desk yourself.'*\n"
	)

	# Inject the deep ERPNext knowledge base when ERPNext is installed.
	kb = _get_erpnext_kb(apps["apps"])
	if kb:
		parts.append(kb)

	# Inject Appe mobile-app module knowledge (always — this IS the Appe app).
	parts.append(_get_appe_kb())

	# Frappe ecosystem docs, GitHub links, installed apps reference.
	parts.append(_get_ecosystem_kb(apps["apps"]))

	return "\n".join(parts)


def _is_user_allowed(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	allowed = set(_settings().get_allowed_roles())
	if not allowed:
		return True
	roles = set(frappe.get_roles(user))
	return bool(roles & allowed)


def _context_block(context: dict | str | None) -> str | None:
	if not context:
		return None
	if isinstance(context, str):
		try:
			context = json.loads(context)
		except Exception:
			return f"Conversation context: {context}"
	try:
		dumped = json.dumps(context, indent=2, default=str)
	except Exception:
		dumped = str(context)
	return f"Conversation context (read-only, from the mobile app):\n```json\n{dumped}\n```"


def _build_messages_for_provider(conversation, system_prompt: str) -> list[dict]:
	out: list[dict] = []
	out.append({"role": "system", "content": system_prompt})
	ctx_block = _context_block(conversation.context)
	if ctx_block:
		out.append({"role": "system", "content": ctx_block})

	# Walk through history, grouping assistant tool_calls with their tool responses
	pending_assistant: dict | None = None
	for row in conversation.messages or []:
		role = row.role
		if role == "assistant":
			if pending_assistant:
				out.append(pending_assistant)
				pending_assistant = None
			msg: dict[str, Any] = {"role": "assistant", "content": row.content or ""}
			if row.tool_name:
				args = {}
				try:
					args = json.loads(row.tool_arguments or "{}")
				except Exception:
					args = {}
				msg["tool_calls"] = [
					{
						"id": row.tool_call_id or "",
						"type": "function",
						"function": {
							"name": row.tool_name,
							"arguments": json.dumps(args),
						},
						# Internal-friendly fields (used by Anthropic/Gemini providers):
						"name": row.tool_name,
						"arguments": args,
					}
				]
			out.append(msg)
		elif role == "tool":
			out.append(
				{
					"role": "tool",
					"tool_call_id": row.tool_call_id or "",
					"tool_name": row.tool_name or "",
					"content": row.tool_result or row.content or "",
				}
			)
		elif role == "user":
			out.append({"role": "user", "content": row.content or ""})
		elif role == "system":
			out.append({"role": "system", "content": row.content or ""})
	return out


def _serialize_tool_result(result: dict) -> str:
	try:
		return json.dumps(result, default=str)
	except Exception:
		return str(result)


def _persist_assistant_text(conversation, text: str, model: str, tokens: int):
	conversation.add_message(role="assistant", content=text or "", tokens_used=tokens, model=model)


def _persist_assistant_tool_call(conversation, tool_call: dict, model: str):
	conversation.add_message(
		role="assistant",
		content="",
		tool_name=tool_call.get("name"),
		tool_call_id=tool_call.get("id"),
		tool_arguments=json.dumps(tool_call.get("arguments") or {}, default=str),
		model=model,
	)


def _persist_tool_result(conversation, tool_call: dict, exec_result: dict):
	conversation.add_message(
		role="tool",
		content="",
		tool_name=tool_call.get("name"),
		tool_call_id=tool_call.get("id"),
		tool_result=_serialize_tool_result(exec_result),
	)


def chat(conversation_name: str, user_message: str) -> dict:
	if not _is_user_allowed():
		frappe.throw("You are not allowed to use Appe Buddy.", frappe.PermissionError)

	settings = _settings()
	if not settings.enabled:
		frappe.throw("Appe Buddy is disabled.")

	conversation = frappe.get_doc("Appe Buddy Conversation", conversation_name)
	if conversation.user != frappe.session.user and "System Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw("You can only chat in your own conversations.", frappe.PermissionError)

	# Append user message
	conversation.add_message(role="user", content=user_message or "")
	conversation.provider = settings.provider
	conversation.model = settings.model
	conversation.update_totals()
	conversation.save(ignore_permissions=False)

	provider = get_provider()
	tools = tool_schemas()

	max_iters = int(settings.max_tool_iterations or 8)
	temperature = float(settings.temperature or 0.2)
	max_tokens = int(settings.max_tokens or 2048)
	system_prompt = _enriched_system_prompt(settings.system_prompt or "You are Appe Buddy.")

	turn_token_total = 0
	final_text: str | None = None

	for _ in range(max_iters):
		messages = _build_messages_for_provider(conversation, system_prompt)
		try:
			result = provider.chat(messages, tools=tools, temperature=temperature, max_tokens=max_tokens)
		except AIProviderError as e:
			conversation.add_message(role="assistant", content=f"[Provider error] {e}", model=settings.model)
			conversation.update_totals()
			conversation.save(ignore_permissions=True)
			frappe.throw(str(e))

		turn_token_total += int(result.get("usage", {}).get("total_tokens") or 0)

		tool_calls = result.get("tool_calls") or []
		if tool_calls:
			# Save assistant message containing the tool_calls
			# (one row per tool call to keep the schema simple)
			for tc in tool_calls:
				_persist_assistant_tool_call(conversation, tc, settings.model)

			# Execute each tool call and append the tool results
			for tc in tool_calls:
				exec_result = execute_tool(
					tc.get("name") or "",
					tc.get("arguments") or {},
					conversation=conversation.name,
				)
				_persist_tool_result(conversation, tc, exec_result)

			conversation.update_totals()
			conversation.save(ignore_permissions=True)
			# Loop again so the model can react to tool results
			continue

		# No tool calls -> final assistant text
		final_text = result.get("content") or ""
		_persist_assistant_text(conversation, final_text, settings.model, turn_token_total)
		conversation.update_totals()
		conversation.save(ignore_permissions=True)
		break
	else:
		# Iteration cap hit
		final_text = "I hit my tool-call limit. Please rephrase or split the task."
		_persist_assistant_text(conversation, final_text, settings.model, turn_token_total)
		conversation.update_totals()
		conversation.save(ignore_permissions=True)

	return {
		"conversation": conversation.name,
		"reply": final_text or "",
		"usage": {"total_tokens": turn_token_total},
		"messages": serialize_messages(conversation.messages[-(2 * max_iters + 4) :]),
	}


def serialize_messages(rows) -> list[dict]:
	out: list[dict] = []
	for r in rows or []:
		out.append(
			{
				"role": r.role,
				"content": r.content or "",
				"tool_name": r.tool_name,
				"tool_call_id": r.tool_call_id,
				"tool_arguments": _safe_json(r.tool_arguments),
				"tool_result": _safe_json(r.tool_result),
				"tokens_used": r.tokens_used or 0,
				"model": r.model,
				"created_at": str(r.created_at) if r.created_at else None,
			}
		)
	return out


def _safe_json(text: str | None):
	if not text:
		return None
	try:
		return json.loads(text)
	except Exception:
		return text
