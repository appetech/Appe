# Copyright (c) 2026, Appe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AppeBuddyConversation(Document):
	def before_insert(self):
		if not self.user:
			self.user = frappe.session.user
		if not self.title:
			self.title = "New Chat"

	def update_totals(self):
		self.total_messages = len(self.messages or [])
		self.total_tokens = sum((m.tokens_used or 0) for m in (self.messages or []))

	def add_message(
		self,
		role: str,
		content: str = "",
		*,
		tool_name: str | None = None,
		tool_call_id: str | None = None,
		tool_arguments: str | None = None,
		tool_result: str | None = None,
		tokens_used: int = 0,
		model: str | None = None,
	):
		row = self.append(
			"messages",
			{
				"role": role,
				"content": content,
				"tool_name": tool_name,
				"tool_call_id": tool_call_id,
				"tool_arguments": tool_arguments,
				"tool_result": tool_result,
				"tokens_used": tokens_used or 0,
				"model": model,
				"created_at": frappe.utils.now_datetime(),
			},
		)
		return row
