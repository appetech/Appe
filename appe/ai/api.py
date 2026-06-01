import json
from typing import Any

import frappe

from . import buddy as _buddy
from .providers import AIProviderError, get_provider


def _settings():
	return frappe.get_cached_doc("Appe Buddy Settings")


def _ok(data: Any = None) -> dict:
	return {"status": True, "data": data}


def _fail(error: str, http: int | None = None) -> dict:
	if http:
		frappe.local.response.http_status_code = http
	return {"status": False, "error": error}


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw("Authentication required", frappe.AuthenticationError)


def _ensure_user_owns(conv) -> None:
	if conv.user != frappe.session.user and "System Manager" not in frappe.get_roles(frappe.session.user):
		frappe.throw("Not allowed", frappe.PermissionError)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


@frappe.whitelist()
def new_conversation(title: str | None = None, context: Any = None) -> dict:
	
	_require_login()
	ctx_str: str | None = None
	if context is not None:
		if isinstance(context, (dict, list)):
			ctx_str = json.dumps(context, default=str)
		else:
			# Validate it's JSON when string-like
			try:
				json.loads(context)
				ctx_str = context
			except Exception:
				ctx_str = json.dumps({"raw": str(context)})

	doc = frappe.get_doc(
		{
			"doctype": "Appe Buddy Conversation",
			"title": (title or "New Chat").strip()[:140] or "New Chat",
			"user": frappe.session.user,
			"context": ctx_str,
		}
	)
	doc.insert(ignore_permissions=False)
	return _ok({"name": doc.name, "title": doc.title, "status": doc.status})


@frappe.whitelist()
def list_conversations(limit: int = 50, status: str | None = None) -> dict:
	_require_login()
	filters: dict = {"user": frappe.session.user}
	if status:
		filters["status"] = status
	rows = frappe.get_all(
		"Appe Buddy Conversation",
		filters=filters,
		fields=[
			"name",
			"title",
			"status",
			"pinned",
			"model",
			"provider",
			"total_messages",
			"total_tokens",
			"modified",
		],
		order_by="pinned desc, modified desc",
		limit_page_length=min(int(limit or 50), 200),
	)
	return _ok(rows)


@frappe.whitelist()
def get_conversation(name: str, message_limit: int = 100) -> dict:
	_require_login()
	doc = frappe.get_doc("Appe Buddy Conversation", name)
	_ensure_user_owns(doc)
	limit = max(1, min(int(message_limit or 100), 500))
	msgs = (doc.messages or [])[-limit:]
	return _ok(
		{
			"name": doc.name,
			"title": doc.title,
			"status": doc.status,
			"pinned": int(doc.pinned or 0),
			"user": doc.user,
			"model": doc.model,
			"provider": doc.provider,
			"total_messages": doc.total_messages or 0,
			"total_tokens": doc.total_tokens or 0,
			"context": _safe_json(doc.context),
			"messages": _buddy.serialize_messages(msgs),
			"modified": str(doc.modified),
		}
	)


@frappe.whitelist()
def rename_conversation(name: str, title: str) -> dict:
	_require_login()
	doc = frappe.get_doc("Appe Buddy Conversation", name)
	_ensure_user_owns(doc)
	doc.title = (title or "").strip()[:140] or doc.title
	doc.save(ignore_permissions=False)
	return _ok({"name": doc.name, "title": doc.title})


@frappe.whitelist()
def archive_conversation(name: str) -> dict:
	_require_login()
	doc = frappe.get_doc("Appe Buddy Conversation", name)
	_ensure_user_owns(doc)
	doc.status = "Archived"
	doc.save(ignore_permissions=False)
	return _ok({"name": doc.name, "status": doc.status})


@frappe.whitelist()
def unarchive_conversation(name: str) -> dict:
	_require_login()
	doc = frappe.get_doc("Appe Buddy Conversation", name)
	_ensure_user_owns(doc)
	doc.status = "Active"
	doc.save(ignore_permissions=False)
	return _ok({"name": doc.name, "status": doc.status})


@frappe.whitelist()
def pin_conversation(name: str, pinned: int | bool = 1) -> dict:
	_require_login()
	doc = frappe.get_doc("Appe Buddy Conversation", name)
	_ensure_user_owns(doc)
	doc.pinned = 1 if str(pinned) not in ("0", "false", "False", "") else 0
	doc.save(ignore_permissions=False)
	return _ok({"name": doc.name, "pinned": int(doc.pinned)})


@frappe.whitelist(methods=["POST", "DELETE"])
def delete_conversation(name: str) -> dict:
	_require_login()
	doc = frappe.get_doc("Appe Buddy Conversation", name)
	_ensure_user_owns(doc)
	frappe.delete_doc("Appe Buddy Conversation", doc.name, ignore_permissions=False)
	return _ok({"name": name, "deleted": True})


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def send_message(
	message: str,
	conversation: str | None = None,
	title: str | None = None,
	context: Any = None,
) -> dict:
	
	_require_login()
	if not message or not message.strip():
		return _fail("message is required", http=400)

	if not conversation:
		conv = new_conversation(title=title or message[:60], context=context)
		conv_name = conv["data"]["name"]
	else:
		# Validate conversation
		conv_doc = frappe.get_doc("Appe Buddy Conversation", conversation)
		_ensure_user_owns(conv_doc)
		# If new context was sent, replace it
		if context is not None:
			if isinstance(context, (dict, list)):
				conv_doc.context = json.dumps(context, default=str)
			elif isinstance(context, str):
				conv_doc.context = context
			conv_doc.save(ignore_permissions=False)
		conv_name = conv_doc.name

	try:
		result = _buddy.chat(conv_name, message)
	except AIProviderError as e:
		return _fail(f"AI provider error: {e}", http=502)
	except frappe.PermissionError as e:
		return _fail(str(e), http=403)
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(), title="Appe Buddy send_message failed")
		return _fail(str(e), http=500)

	return _ok(result)


@frappe.whitelist()
def list_tools() -> dict:
	_require_login()
	from .tools import tool_schemas

	return _ok(tool_schemas())


@frappe.whitelist()
def settings_public() -> dict:
	_require_login()
	s = _settings()
	return _ok(
		{
			"enabled": int(s.enabled or 0),
			"provider": s.provider,
			"model": s.model,
			"max_tokens": s.max_tokens,
			"max_tool_iterations": s.max_tool_iterations,
			"capabilities": {
				"create_doctype": int(s.allow_create_doctype or 0),
				"create_report": int(s.allow_create_report or 0),
				"create_chart": int(s.allow_create_chart or 0),
				"create_dashboard": int(s.allow_create_dashboard or 0),
				"create_number_card": int(s.allow_create_number_card or 0),
				"query_data": int(s.allow_query_data or 0),
				"run_report": int(s.allow_run_report or 0),
			},
		}
	)


@frappe.whitelist()
def test_connection() -> dict:
	_require_login()
	try:
		provider = get_provider()
		result = provider.chat(
			[
				{"role": "system", "content": "Reply with the single word: pong."},
				{"role": "user", "content": "ping"},
			],
			tools=None,
			temperature=0.0,
			max_tokens=16,
		)
		return {
			"ok": True,
			"provider": provider.name,
			"model": provider.model,
			"reply": (result.get("content") or "").strip(),
		}
	except Exception as e:
		return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Mobile-friendly helper endpoints
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def health() -> dict:
	"""Lightweight ping. Useful for mobile splash screens to verify that the
	backend is reachable before attempting login."""
	return _ok(
		{
			"ok": True,
			"app": "appe",
			"time": frappe.utils.now(),
			"site": frappe.local.site,
		}
	)


@frappe.whitelist()
def me() -> dict:
	"""One-shot bootstrap for mobile clients. Returns the logged-in user, their
	roles, and a snapshot of Buddy's public settings & capabilities."""
	_require_login()
	user = frappe.session.user
	udoc = frappe.db.get_value(
		"User",
		user,
		[
			"name",
			"full_name",
			"email",
			"username",
			"user_image",
			"language",
			"time_zone",
			"mobile_no",
		],
		as_dict=True,
	) or {}
	s = _settings()
	return _ok(
		{
			"user": {
				"name": user,
				"full_name": udoc.get("full_name"),
				"email": udoc.get("email"),
				"username": udoc.get("username"),
				"avatar": udoc.get("user_image"),
				"language": udoc.get("language") or "en",
				"time_zone": udoc.get("time_zone"),
				"mobile_no": udoc.get("mobile_no"),
				"roles": frappe.get_roles(user),
			},
			"buddy": {
				"enabled": int(s.enabled or 0),
				"provider": s.provider,
				"model": s.model,
				"max_tokens": s.max_tokens,
				"max_tool_iterations": s.max_tool_iterations,
				"capabilities": {
					"create_doctype": int(s.allow_create_doctype or 0),
					"create_report": int(s.allow_create_report or 0),
					"create_chart": int(s.allow_create_chart or 0),
					"create_dashboard": int(s.allow_create_dashboard or 0),
					"create_number_card": int(s.allow_create_number_card or 0),
					"query_data": int(s.allow_query_data or 0),
					"run_report": int(s.allow_run_report or 0),
				},
			},
			"erpnext": {
				"installed": "erpnext" in frappe.get_installed_apps(),
				"default_company": frappe.defaults.get_user_default("Company"),
				"default_currency": frappe.defaults.get_user_default("Currency")
				or frappe.db.get_default("currency"),
			},
		}
	)


@frappe.whitelist()
def suggest_prompts(context: Any = None, limit: int = 6) -> dict:
	"""Return starter prompts based on the user's environment + context.
	Mobile UI can show these as chips above the empty chat state."""
	_require_login()
	limit = max(1, min(int(limit or 6), 12))
	apps = frappe.get_installed_apps()
	prompts: list[str] = [
		"Build me a Sales report grouped by Customer for last 30 days",
		"Create a Number Card for total Sales Invoice this month",
		"Show top 5 customers by revenue this fiscal year",
		"List all overdue Sales Invoices",
		"Summarize my pending Tasks",
	]
	if "erpnext" in apps:
		prompts = [
			"Total receivable amount kya hai?",
			"Top 5 customers by revenue this fiscal year",
			"Show outstanding Sales Invoices over 30 days old",
			"Build a chart of monthly sales for the current fiscal year",
			"Create a Number Card for total Sales Invoice this month",
			"Show today's stock movements",
		]
	if "hrms" in apps:
		prompts.append("Show pending Leave Applications for my team")

	# Context-aware prompts when the mobile app sends current screen info.
	ctx = context if isinstance(context, dict) else _safe_json(context) or {}
	if isinstance(ctx, dict):
		dt = ctx.get("doctype")
		dn = ctx.get("docname")
		if dt and dn:
			prompts.insert(0, f"Summarize {dt} {dn}")
			prompts.insert(1, f"What is the status and pending actions for {dt} {dn}?")
		elif dt:
			prompts.insert(0, f"Show me the latest {dt} records")

	return _ok(prompts[:limit])


@frappe.whitelist()
def search_messages(q: str, limit: int = 30) -> dict:
	"""Free-text search across the user's own messages. Returns matches with
	their conversation so the mobile app can deep-link straight into the chat."""
	_require_login()
	q = (q or "").strip()
	if not q:
		return _ok([])
	limit = max(1, min(int(limit or 30), 100))
	rows = frappe.db.sql(
		"""
		SELECT m.parent AS conversation,
		       m.role,
		       LEFT(m.content, 220) AS snippet,
		       m.created_at,
		       c.title AS conversation_title
		FROM `tabAppe Buddy Message` m
		INNER JOIN `tabAppe Buddy Conversation` c ON c.name = m.parent
		WHERE c.user = %(user)s
		  AND m.content LIKE %(like)s
		ORDER BY m.created_at DESC
		LIMIT %(limit)s
		""",
		{"user": frappe.session.user, "like": f"%{q}%", "limit": limit},
		as_dict=True,
	)
	return _ok(rows)


@frappe.whitelist(methods=["POST"])
def bulk_archive(names: Any) -> dict:
	"""Archive many conversations in one call. `names` may be a JSON array or a
	comma-separated string."""
	_require_login()
	names_list = _coerce_list(names)
	updated = []
	for n in names_list:
		try:
			doc = frappe.get_doc("Appe Buddy Conversation", n)
			_ensure_user_owns(doc)
			doc.status = "Archived"
			doc.save(ignore_permissions=False)
			updated.append(n)
		except Exception:
			continue
	return _ok({"archived": updated, "count": len(updated)})


@frappe.whitelist(methods=["POST", "DELETE"])
def bulk_delete(names: Any) -> dict:
	"""Delete many conversations in one call."""
	_require_login()
	names_list = _coerce_list(names)
	deleted = []
	for n in names_list:
		try:
			doc = frappe.get_doc("Appe Buddy Conversation", n)
			_ensure_user_owns(doc)
			frappe.delete_doc("Appe Buddy Conversation", doc.name, ignore_permissions=False)
			deleted.append(n)
		except Exception:
			continue
	return _ok({"deleted": deleted, "count": len(deleted)})


@frappe.whitelist()
def export_conversation(name: str, format: str = "markdown") -> dict:
	"""Export a conversation as `markdown` or `json`. Mobile apps can use this
	to share / save chat transcripts."""
	_require_login()
	doc = frappe.get_doc("Appe Buddy Conversation", name)
	_ensure_user_owns(doc)
	msgs = doc.messages or []
	if (format or "markdown").lower() == "json":
		return _ok(
			{
				"format": "json",
				"conversation": {
					"name": doc.name,
					"title": doc.title,
					"user": doc.user,
					"created": str(doc.creation),
					"messages": _buddy.serialize_messages(msgs),
				},
			}
		)
	# Markdown export
	lines = [f"# {doc.title}", f"_Exported {frappe.utils.now()}_", ""]
	for m in msgs:
		role = (m.role or "user").capitalize()
		lines.append(f"## {role}")
		if m.role == "tool":
			lines.append(f"_Tool: `{m.tool_name or ''}`_")
			if m.tool_arguments:
				lines.append("```json")
				lines.append((m.tool_arguments or "")[:4000])
				lines.append("```")
			if m.tool_result:
				lines.append("```json")
				lines.append((m.tool_result or "")[:4000])
				lines.append("```")
		else:
			lines.append(m.content or "")
		lines.append("")
	return _ok({"format": "markdown", "name": doc.name, "title": doc.title, "body": "\n".join(lines)})


@frappe.whitelist(methods=["POST"])
def feedback(conversation: str, message_index: int, kind: str, comment: str | None = None) -> dict:
	"""Record thumbs up/down feedback on a specific assistant message.
	`kind` should be `up`, `down` or `flag`. Stored as a comment on the
	conversation so it shows up in the audit trail."""
	_require_login()
	doc = frappe.get_doc("Appe Buddy Conversation", conversation)
	_ensure_user_owns(doc)
	kind = (kind or "up").lower()
	if kind not in ("up", "down", "flag"):
		return _fail("kind must be one of: up, down, flag", http=400)
	emoji = {"up": "👍", "down": "👎", "flag": "🚩"}[kind]
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": "Appe Buddy Conversation",
			"reference_name": doc.name,
			"content": f"{emoji} Feedback ({kind}) on message #{message_index}: {comment or ''}",
			"comment_email": frappe.session.user,
			"comment_by": frappe.session.user,
		}
	).insert(ignore_permissions=True)
	return _ok({"recorded": True, "kind": kind})


@frappe.whitelist()
def list_provider_models_public(provider: str | None = None) -> dict:
	"""Mobile-friendly mirror of the Settings model browser. Returns the list of
	models supported by a given provider. Falls back to curated lists when a
	live provider listing isn't available."""
	_require_login()
	from .doctype.appe_buddy_settings.appe_buddy_settings import list_provider_models  # type: ignore

	try:
		out = list_provider_models(provider=provider)
		return _ok(out)
	except Exception as e:
		return _fail(str(e), http=500)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _coerce_list(value: Any) -> list[str]:
	if isinstance(value, list):
		return [str(v) for v in value if v]
	if isinstance(value, str):
		v = value.strip()
		try:
			parsed = json.loads(v)
			if isinstance(parsed, list):
				return [str(x) for x in parsed if x]
		except Exception:
			pass
		return [s.strip() for s in v.split(",") if s.strip()]
	return []


def _safe_json(text: str | None):
	if not text:
		return None
	try:
		return json.loads(text)
	except Exception:
		return text
