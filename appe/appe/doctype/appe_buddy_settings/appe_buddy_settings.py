# Copyright (c) 2026, Appe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


PROVIDER_PRESETS: dict[str, dict] = {
	"OpenAI": {
		"model": "gpt-4o-mini",
		"api_base_url": "https://api.openai.com/v1",
		"models": [
			"gpt-4o-mini",
			"gpt-4o",
			"gpt-4.1-mini",
			"gpt-4.1",
			"gpt-4-turbo",
			"o4-mini",
			"o3-mini",
		],
	},
	"OpenAI Compatible": {
		"model": "gpt-4o-mini",
		"api_base_url": "",
		"models": [
			"gpt-4o-mini",
			"gpt-4o",
			"llama-3.1-70b-instruct",
			"llama-3.1-8b-instruct",
			"mixtral-8x7b-instruct",
			"qwen2.5-72b-instruct",
		],
	},
	"Anthropic": {
		"model": "claude-3-5-sonnet-20241022",
		"api_base_url": "https://api.anthropic.com/v1",
		"models": [
			"claude-3-5-sonnet-20241022",
			"claude-3-5-haiku-20241022",
			"claude-3-opus-20240229",
			"claude-3-haiku-20240307",
		],
	},
	"Gemini": {
		# gemini-1.5-* family was deprecated by Google. Current default uses 2.5-flash
		# which is fast, cheap, and supports tool calling.
		"model": "gemini-2.5-flash",
		"api_base_url": "https://generativelanguage.googleapis.com/v1beta",
		"models": [
			"gemini-2.5-flash",
			"gemini-2.5-pro",
			"gemini-2.5-flash-lite",
			"gemini-2.0-flash",
			"gemini-2.0-flash-lite",
			"gemini-flash-latest",
			"gemini-pro-latest",
			"gemini-flash-lite-latest",
		],
	},
}


# Models known to be retired by providers — we will auto-upgrade them to a
# safe modern default and log a notice for the user.
DEPRECATED_MODELS: dict[str, str] = {
	# Gemini 1.5 family was sunset by Google in 2025 / early 2026.
	"gemini-1.5-flash": "gemini-2.5-flash",
	"gemini-1.5-flash-8b": "gemini-2.5-flash",
	"gemini-1.5-flash-latest": "gemini-flash-latest",
	"gemini-1.5-pro": "gemini-2.5-pro",
	"gemini-1.5-pro-latest": "gemini-pro-latest",
	# OpenAI legacy chat models
	"gpt-3.5-turbo": "gpt-4o-mini",
	"gpt-3.5-turbo-16k": "gpt-4o-mini",
	# Old Anthropic Claude 2 / Instant
	"claude-2": "claude-3-5-sonnet-20241022",
	"claude-2.1": "claude-3-5-sonnet-20241022",
	"claude-instant-1.2": "claude-3-5-haiku-20241022",
}


class AppeBuddySettings(Document):
	def before_save(self):
		"""Apply provider presets when the user hasn't picked a model/base URL,
		and auto-upgrade known-deprecated models so requests don't 404."""
		provider = (self.provider or "OpenAI").strip()
		preset = PROVIDER_PRESETS.get(provider) or {}

		current_model = (self.model or "").strip()
		if not current_model:
			self.model = preset.get("model") or "gpt-4o-mini"
		elif current_model in DEPRECATED_MODELS:
			# Auto-upgrade silently — surface a one-time msgprint so the admin knows
			upgraded = DEPRECATED_MODELS[current_model]
			self.model = upgraded
			try:
				frappe.msgprint(
					frappe._(
						"Model <b>{0}</b> has been retired by {1}. Upgraded to <b>{2}</b>."
					).format(current_model, provider, upgraded),
					alert=True,
					indicator="orange",
				)
			except Exception:
				pass

		# Only auto-fill base URL when blank AND provider has a sensible default
		if not (self.api_base_url or "").strip() and preset.get("api_base_url"):
			self.api_base_url = preset["api_base_url"]

	def validate(self):
		if self.temperature is None:
			self.temperature = 0.2
		if self.temperature < 0:
			self.temperature = 0
		if self.temperature > 2:
			self.temperature = 2

		if not self.max_tokens or self.max_tokens < 64:
			self.max_tokens = 2048
		if not self.max_tool_iterations or self.max_tool_iterations < 1:
			self.max_tool_iterations = 8
		if not self.max_query_rows or self.max_query_rows < 1:
			self.max_query_rows = 200
		if not self.request_timeout or self.request_timeout < 5:
			self.request_timeout = 60

	def get_api_key(self) -> str:
		"""Return the decrypted API key for the configured provider."""
		return self.get_password("api_key", raise_exception=False) or ""

	def get_allowed_roles(self) -> list[str]:
		raw = (self.allowed_roles or "System Manager").strip()
		return [r.strip() for r in raw.split(",") if r.strip()]

	def get_blocked_doctypes(self) -> set[str]:
		raw = (self.blocked_doctypes or "").strip()
		return {d.strip() for d in raw.split(",") if d.strip()}


# ---------------------------------------------------------------------------
# Server-side helpers used by the Settings UI / API
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_provider_preset(provider: str | None = None) -> dict:
	"""Return preset (default model, base URL, suggested model list) for a provider."""
	preset = PROVIDER_PRESETS.get((provider or "OpenAI").strip()) or {}
	return {
		"provider": provider,
		"model": preset.get("model") or "",
		"api_base_url": preset.get("api_base_url") or "",
		"models": preset.get("models") or [],
	}


@frappe.whitelist()
def list_provider_models(provider: str | None = None) -> dict:
	"""Try to fetch the live model list from the configured provider.

	For OpenAI / OpenAI-compatible this hits ``/v1/models``. For other providers
	we fall back to the curated preset list to avoid surprise API costs.
	"""
	frappe.only_for("System Manager")
	s = frappe.get_cached_doc("Appe Buddy Settings")
	prov = (provider or s.provider or "OpenAI").strip()
	preset = PROVIDER_PRESETS.get(prov) or {}

	if prov in ("OpenAI", "OpenAI Compatible"):
		import requests

		api_key = s.get_api_key()
		base = (s.api_base_url or preset.get("api_base_url") or "https://api.openai.com/v1").rstrip("/")
		if not api_key:
			return {
				"source": "preset",
				"models": preset.get("models") or [],
				"hint": "API key not set. Showing curated defaults.",
			}
		try:
			r = requests.get(
				f"{base}/models",
				headers={"Authorization": f"Bearer {api_key}"},
				timeout=int(s.request_timeout or 30),
			)
			if r.status_code >= 400:
				return {
					"source": "preset",
					"models": preset.get("models") or [],
					"hint": f"Provider returned HTTP {r.status_code}. Showing defaults.",
				}
			data = r.json() or {}
			ids = sorted({m.get("id") for m in (data.get("data") or []) if m.get("id")})
			# Filter to chat-capable IDs heuristically for OpenAI
			if prov == "OpenAI":
				ids = [
					m
					for m in ids
					if any(p in m for p in ("gpt-", "o3", "o4", "chatgpt", "omni"))
				]
			return {"source": "live", "models": ids[:200]}
		except Exception as e:
			return {
				"source": "preset",
				"models": preset.get("models") or [],
				"hint": f"Could not reach provider ({e}). Showing defaults.",
			}

	if prov == "Gemini":
		import requests

		api_key = s.get_api_key()
		base = (s.api_base_url or preset.get("api_base_url") or "https://generativelanguage.googleapis.com/v1beta").rstrip(
			"/"
		)
		if not api_key:
			return {
				"source": "preset",
				"models": preset.get("models") or [],
				"hint": "API key not set. Showing curated defaults.",
			}
		try:
			r = requests.get(
				f"{base}/models?key={api_key}",
				timeout=int(s.request_timeout or 30),
			)
			if r.status_code >= 400:
				return {
					"source": "preset",
					"models": preset.get("models") or [],
					"hint": f"Provider returned HTTP {r.status_code}. Showing defaults.",
				}
			data = r.json() or {}
			out = []
			for m in data.get("models") or []:
				methods = m.get("supportedGenerationMethods") or []
				if "generateContent" not in methods:
					continue
				name = (m.get("name") or "").replace("models/", "")
				if not name:
					continue
				# Exclude tts / image / embedding / experimental robotics models
				lname = name.lower()
				if any(
					p in lname
					for p in (
						"-tts",
						"-image",
						"embedding",
						"aqa",
						"robotics",
						"lyria",
						"nano-banana",
						"computer-use",
						"deep-research",
						"antigravity",
					)
				):
					continue
				out.append(name)
			# Stable order: latest-marked first, then version-sort descending
			def sort_key(n):
				return (
					not n.endswith("latest"),
					not n.startswith("gemini-3"),
					not n.startswith("gemini-2.5"),
					n,
				)

			out.sort(key=sort_key)
			return {"source": "live", "models": out[:60]}
		except Exception as e:
			return {
				"source": "preset",
				"models": preset.get("models") or [],
				"hint": f"Could not reach provider ({e}). Showing defaults.",
			}

	# Anthropic doesn't have a public list endpoint — curated list only.
	return {"source": "preset", "models": preset.get("models") or []}


@frappe.whitelist()
def get_stats() -> dict:
	"""Aggregate usage stats for the Settings dashboard panel."""
	frappe.only_for(["System Manager"])
	totals_sql = frappe.db.sql(
		"""
		SELECT
			COUNT(*) AS conversations,
			COALESCE(SUM(total_messages), 0) AS messages,
			COALESCE(SUM(total_tokens), 0) AS tokens,
			MAX(modified) AS last_used
		FROM `tabAppe Buddy Conversation`
		""",
		as_dict=True,
	)[0]

	top_users = frappe.db.sql(
		"""
		SELECT user, COUNT(*) AS conversations, COALESCE(SUM(total_tokens), 0) AS tokens
		FROM `tabAppe Buddy Conversation`
		GROUP BY user
		ORDER BY tokens DESC, conversations DESC
		LIMIT 10
		""",
		as_dict=True,
	)

	tool_usage = frappe.db.sql(
		"""
		SELECT tool_name,
		       COUNT(*) AS calls,
		       SUM(CASE WHEN status = 'Success' THEN 1 ELSE 0 END) AS success,
		       SUM(CASE WHEN status = 'Error' THEN 1 ELSE 0 END) AS errors,
		       SUM(CASE WHEN status = 'Blocked' THEN 1 ELSE 0 END) AS blocked,
		       ROUND(AVG(duration_ms), 1) AS avg_ms
		FROM `tabAppe Buddy Tool Log`
		GROUP BY tool_name
		ORDER BY calls DESC
		LIMIT 20
		""",
		as_dict=True,
	)

	last_7d_tokens = frappe.db.sql(
		"""
		SELECT DATE(modified) AS day, COALESCE(SUM(total_tokens), 0) AS tokens
		FROM `tabAppe Buddy Conversation`
		WHERE modified >= DATE_SUB(NOW(), INTERVAL 7 DAY)
		GROUP BY DATE(modified)
		ORDER BY day
		""",
		as_dict=True,
	)

	return {
		"totals": {
			"conversations": int(totals_sql.get("conversations") or 0),
			"messages": int(totals_sql.get("messages") or 0),
			"tokens": int(totals_sql.get("tokens") or 0),
			"last_used": str(totals_sql.get("last_used") or ""),
		},
		"top_users": top_users,
		"tool_usage": tool_usage,
		"daily_tokens_7d": [
			{"day": str(r.get("day")), "tokens": int(r.get("tokens") or 0)} for r in last_7d_tokens
		],
	}
