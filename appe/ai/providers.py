from __future__ import annotations

import json
from typing import Any

import frappe
import requests


OPENAI_DEFAULT_BASE = "https://api.openai.com/v1"
ANTHROPIC_DEFAULT_BASE = "https://api.anthropic.com/v1"
GEMINI_DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"


class AIProviderError(Exception):
	pass


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class BaseProvider:
	name: str = "base"

	def __init__(self, api_key: str, model: str, base_url: str | None = None, timeout: int = 60):
		self.api_key = api_key
		self.model = model
		self.base_url = (base_url or "").rstrip("/") or self._default_base()
		self.timeout = timeout or 60

	def _default_base(self) -> str:
		raise NotImplementedError

	def chat(
		self,
		messages: list[dict],
		tools: list[dict] | None = None,
		temperature: float = 0.2,
		max_tokens: int = 2048,
	) -> dict:
		raise NotImplementedError


# ---------------------------------------------------------------------------
# OpenAI (and OpenAI-compatible: Azure-style /v1, Ollama, vLLM, OpenRouter, ...)
# ---------------------------------------------------------------------------


class OpenAIProvider(BaseProvider):
	name = "OpenAI"

	def _default_base(self) -> str:
		return OPENAI_DEFAULT_BASE

	def chat(self, messages, tools=None, temperature=0.2, max_tokens=2048):
		url = f"{self.base_url}/chat/completions"
		headers = {
			"Authorization": f"Bearer {self.api_key}",
			"Content-Type": "application/json",
		}
		payload: dict[str, Any] = {
			"model": self.model,
			"messages": messages,
			"temperature": float(temperature),
			"max_tokens": int(max_tokens),
		}
		if tools:
			payload["tools"] = [{"type": "function", "function": t} for t in tools]
			payload["tool_choice"] = "auto"

		try:
			resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
		except requests.RequestException as e:
			raise AIProviderError(f"OpenAI network error: {e}") from e

		if resp.status_code >= 400:
			body = resp.text or ""
			lower = body.lower()
			hint = ""
			if resp.status_code == 404 and ("model" in lower or "not found" in lower):
				hint = (
					" — Model not available. Open Appe Buddy Settings → 'Browse Models' "
					"and pick one supported by your account (e.g. gpt-4o-mini, gpt-4o)."
				)
			elif resp.status_code == 401:
				hint = " — Invalid API key. Update it in Appe Buddy Settings."
			elif resp.status_code == 429:
				hint = " — Rate-limited / quota exceeded. Try a smaller model or wait."
			raise AIProviderError(f"OpenAI HTTP {resp.status_code}: {body[:400]}{hint}")
		data = resp.json()
		choice = (data.get("choices") or [{}])[0]
		msg = choice.get("message") or {}
		tool_calls = []
		for tc in msg.get("tool_calls") or []:
			fn = tc.get("function") or {}
			args_str = fn.get("arguments") or "{}"
			try:
				args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
			except Exception:
				args = {"_raw": args_str}
			tool_calls.append(
				{
					"id": tc.get("id") or "",
					"name": fn.get("name") or "",
					"arguments": args or {},
				}
			)
		usage = data.get("usage") or {}
		return {
			"content": msg.get("content"),
			"tool_calls": tool_calls,
			"usage": {
				"prompt_tokens": usage.get("prompt_tokens") or 0,
				"completion_tokens": usage.get("completion_tokens") or 0,
				"total_tokens": usage.get("total_tokens") or 0,
			},
			"raw": data,
			"model": data.get("model") or self.model,
		}


class OpenAICompatibleProvider(OpenAIProvider):
	name = "OpenAI Compatible"


# ---------------------------------------------------------------------------
# Anthropic Claude
# ---------------------------------------------------------------------------


class AnthropicProvider(BaseProvider):
	name = "Anthropic"

	def _default_base(self) -> str:
		return ANTHROPIC_DEFAULT_BASE

	@staticmethod
	def _convert_messages(messages: list[dict]) -> tuple[str | None, list[dict]]:
		system_prompt: str | None = None
		out: list[dict] = []
		# Anthropic uses a separate `system` field and content blocks.
		# Map tool messages to user role with tool_result content.
		for m in messages:
			role = m.get("role")
			if role == "system":
				system_prompt = (
					(system_prompt + "\n\n" + (m.get("content") or "")) if system_prompt else m.get("content") or ""
				)
				continue
			if role == "tool":
				out.append(
					{
						"role": "user",
						"content": [
							{
								"type": "tool_result",
								"tool_use_id": m.get("tool_call_id") or "",
								"content": m.get("content") or "",
							}
						],
					}
				)
				continue
			if role == "assistant":
				blocks: list[dict] = []
				if m.get("content"):
					blocks.append({"type": "text", "text": m["content"]})
				for tc in m.get("tool_calls") or []:
					try:
						args = tc.get("arguments") or {}
						if isinstance(args, str):
							args = json.loads(args)
					except Exception:
						args = {}
					blocks.append(
						{
							"type": "tool_use",
							"id": tc.get("id") or "",
							"name": tc.get("name") or "",
							"input": args or {},
						}
					)
				if not blocks:
					blocks.append({"type": "text", "text": ""})
				out.append({"role": "assistant", "content": blocks})
				continue
			# user / default
			out.append({"role": "user", "content": m.get("content") or ""})
		return system_prompt, out

	def chat(self, messages, tools=None, temperature=0.2, max_tokens=2048):
		system_prompt, converted = self._convert_messages(messages)
		url = f"{self.base_url}/messages"
		headers = {
			"x-api-key": self.api_key,
			"anthropic-version": "2023-06-01",
			"Content-Type": "application/json",
		}
		payload: dict[str, Any] = {
			"model": self.model,
			"messages": converted,
			"max_tokens": int(max_tokens),
			"temperature": float(temperature),
		}
		if system_prompt:
			payload["system"] = system_prompt
		if tools:
			payload["tools"] = [
				{
					"name": t["name"],
					"description": t.get("description") or "",
					"input_schema": t.get("parameters") or {"type": "object", "properties": {}},
				}
				for t in tools
			]

		try:
			resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
		except requests.RequestException as e:
			raise AIProviderError(f"Anthropic network error: {e}") from e

		if resp.status_code >= 400:
			body = resp.text or ""
			lower = body.lower()
			hint = ""
			if resp.status_code == 404 and ("not_found" in lower or "model" in lower):
				hint = (
					" — Model not available. In Appe Buddy Settings pick a current Claude "
					"(e.g. claude-3-5-sonnet-20241022 or claude-3-5-haiku-20241022)."
				)
			elif resp.status_code == 401:
				hint = " — Invalid Anthropic API key."
			elif resp.status_code == 429:
				hint = " — Rate-limited by Anthropic."
			raise AIProviderError(f"Anthropic HTTP {resp.status_code}: {body[:400]}{hint}")
		data = resp.json()
		content_text_parts: list[str] = []
		tool_calls: list[dict] = []
		for block in data.get("content") or []:
			if block.get("type") == "text":
				content_text_parts.append(block.get("text") or "")
			elif block.get("type") == "tool_use":
				tool_calls.append(
					{
						"id": block.get("id") or "",
						"name": block.get("name") or "",
						"arguments": block.get("input") or {},
					}
				)
		usage = data.get("usage") or {}
		return {
			"content": "\n".join(p for p in content_text_parts if p) or None,
			"tool_calls": tool_calls,
			"usage": {
				"prompt_tokens": usage.get("input_tokens") or 0,
				"completion_tokens": usage.get("output_tokens") or 0,
				"total_tokens": (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0),
			},
			"raw": data,
			"model": data.get("model") or self.model,
		}


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------


class GeminiProvider(BaseProvider):
	name = "Gemini"

	def _default_base(self) -> str:
		return GEMINI_DEFAULT_BASE

	@staticmethod
	def _sanitize_schema(schema):
		
		if isinstance(schema, dict):
			out = {}
			for k, v in schema.items():
				if k in ("default", "additionalProperties"):
					continue
				out[k] = GeminiProvider._sanitize_schema(v)
			t = out.get("type")
			if t == "array" and "items" not in out:
				out["items"] = {"type": "string"}
			if t == "object" and "properties" not in out:
				out["properties"] = {}
			return out
		if isinstance(schema, list):
			return [GeminiProvider._sanitize_schema(x) for x in schema]
		return schema

	@staticmethod
	def _convert_messages(messages: list[dict]) -> tuple[str | None, list[dict]]:
		system_prompt: str | None = None
		out: list[dict] = []
		for m in messages:
			role = m.get("role")
			if role == "system":
				system_prompt = (
					(system_prompt + "\n\n" + (m.get("content") or "")) if system_prompt else m.get("content") or ""
				)
				continue
			if role == "tool":
				# Gemini expects functionResponse parts
				try:
					result = json.loads(m.get("content") or "{}")
				except Exception:
					result = {"result": m.get("content") or ""}
				out.append(
					{
						"role": "user",
						"parts": [
							{
								"functionResponse": {
									"name": m.get("tool_name") or "",
									"response": result if isinstance(result, dict) else {"result": result},
								}
							}
						],
					}
				)
				continue
			if role == "assistant":
				parts: list[dict] = []
				if m.get("content"):
					parts.append({"text": m["content"]})
				for tc in m.get("tool_calls") or []:
					args = tc.get("arguments") or {}
					if isinstance(args, str):
						try:
							args = json.loads(args)
						except Exception:
							args = {}
					parts.append({"functionCall": {"name": tc.get("name") or "", "args": args or {}}})
				if not parts:
					parts.append({"text": ""})
				out.append({"role": "model", "parts": parts})
				continue
			out.append({"role": "user", "parts": [{"text": m.get("content") or ""}]})
		return system_prompt, out

	def chat(self, messages, tools=None, temperature=0.2, max_tokens=2048):
		system_prompt, contents = self._convert_messages(messages)
		url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
		headers = {"Content-Type": "application/json"}
		payload: dict[str, Any] = {
			"contents": contents,
			"generationConfig": {
				"temperature": float(temperature),
				"maxOutputTokens": int(max_tokens),
			},
		}
		if system_prompt:
			payload["systemInstruction"] = {"role": "system", "parts": [{"text": system_prompt}]}
		if tools:
			payload["tools"] = [
				{
					"functionDeclarations": [
						{
							"name": t["name"],
							"description": t.get("description") or "",
							"parameters": self._sanitize_schema(
								t.get("parameters") or {"type": "object", "properties": {}}
							),
						}
						for t in tools
					]
				}
			]

		try:
			resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
		except requests.RequestException as e:
			raise AIProviderError(f"Gemini network error: {e}") from e

		if resp.status_code >= 400:
			body = resp.text or ""
			hint = ""
			lower = body.lower()
			if resp.status_code == 404 and ("not found" in lower or "is not supported" in lower):
				hint = (
					" — The selected Gemini model is unavailable. Open "
					"Appe Buddy Settings → 'Browse Models' and pick a current one "
					"(e.g. gemini-2.5-flash, gemini-flash-latest)."
				)
			elif resp.status_code == 403:
				hint = " — Check that the Gemini API key has access in your Google AI Studio project."
			elif resp.status_code == 429:
				hint = " — Rate limited by Gemini. Try a lighter model (gemini-flash-lite-latest) or wait."
			raise AIProviderError(f"Gemini HTTP {resp.status_code}: {body[:400]}{hint}")
		data = resp.json()
		text_parts: list[str] = []
		tool_calls: list[dict] = []
		candidates = data.get("candidates") or []
		if candidates:
			content = candidates[0].get("content") or {}
			for i, part in enumerate(content.get("parts") or []):
				if "text" in part:
					text_parts.append(part.get("text") or "")
				if "functionCall" in part:
					fc = part["functionCall"]
					tool_calls.append(
						{
							"id": f"call_{i}",
							"name": fc.get("name") or "",
							"arguments": fc.get("args") or {},
						}
					)
		usage = data.get("usageMetadata") or {}
		return {
			"content": "\n".join(p for p in text_parts if p) or None,
			"tool_calls": tool_calls,
			"usage": {
				"prompt_tokens": usage.get("promptTokenCount") or 0,
				"completion_tokens": usage.get("candidatesTokenCount") or 0,
				"total_tokens": usage.get("totalTokenCount") or 0,
			},
			"raw": data,
			"model": self.model,
		}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_provider() -> BaseProvider:
	settings = frappe.get_cached_doc("Appe Buddy Settings")
	if not settings.enabled:
		raise AIProviderError("Appe Buddy is disabled in settings.")
	api_key = settings.get_api_key()
	if not api_key:
		raise AIProviderError("Appe Buddy API key is not configured.")
	model = settings.model
	if not model:
		raise AIProviderError("Appe Buddy model is not configured.")
	base_url = settings.api_base_url or None
	timeout = int(settings.request_timeout or 60)

	provider = (settings.provider or "OpenAI").strip()
	if provider == "OpenAI":
		return OpenAIProvider(api_key, model, base_url, timeout)
	if provider == "OpenAI Compatible":
		return OpenAICompatibleProvider(api_key, model, base_url, timeout)
	if provider == "Anthropic":
		return AnthropicProvider(api_key, model, base_url, timeout)
	if provider == "Gemini":
		return GeminiProvider(api_key, model, base_url, timeout)
	raise AIProviderError(f"Unsupported provider: {provider}")
