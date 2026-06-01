// Copyright (c) 2026, Appe Technologies and contributors
// For license information, please see license.txt
//
// Appe Buddy — full-page Desk chat.
// Features:
//   • Markdown rendering (headers, bold/italic, lists, tables, code, links)
//   • Tool result rendering as data tables when rows are present
//   • Conversation search + date grouping (Today / Yesterday / This Week / Older)
//   • Copy message, Regenerate last reply, Send via Enter, Shift+Enter for newline
//   • Voice input via Web Speech API (Chrome/Edge)
//   • Token usage display in header
//   • Settings shortcut button
//   • Auto-resize textarea

frappe.provide("appe.buddy");

frappe.pages["appe-buddy"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Appe Buddy"),
		single_column: true,
	});
	const ui = new appe.buddy.ChatUI(page);
	ui.render();
	wrapper.appe_buddy_ui = ui;
};

frappe.pages["appe-buddy"].on_page_show = function (wrapper) {
	if (wrapper.appe_buddy_ui) wrapper.appe_buddy_ui.maybe_load_initial();
};

// ===========================================================================
// Tiny markdown renderer (safe-ish — we always html-escape first)
// ===========================================================================

appe.buddy.renderMarkdown = function (raw) {
	if (raw == null) return "";
	let text = String(raw);
	const codeBlocks = [];
	text = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
		codeBlocks.push({ lang, code });
		return `\u0000CODEBLOCK${codeBlocks.length - 1}\u0000`;
	});
	const inlineCodes = [];
	text = text.replace(/`([^`\n]+)`/g, (_, code) => {
		inlineCodes.push(code);
		return `\u0000INLINECODE${inlineCodes.length - 1}\u0000`;
	});

	let html = frappe.utils.escape_html(text);

	// Tables (GFM-ish): | a | b |\n|---|---|\n| x | y |
	html = html.replace(
		/(^|\n)((?:\|[^\n]+\|\n)(?:\|[\s:|-]+\|\n)(?:\|[^\n]*\|\n?)+)/g,
		(_, lead, tbl) => lead + renderMdTable(tbl)
	);

	// Headings ## / ###
	html = html
		.replace(/^###\s+(.+)$/gm, "<h5>$1</h5>")
		.replace(/^##\s+(.+)$/gm, "<h4>$1</h4>")
		.replace(/^#\s+(.+)$/gm, "<h3>$1</h3>");

	// Bold / italic
	html = html
		.replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>")
		.replace(/(^|\s)\*([^*\n]+)\*(?=\s|$)/g, "$1<i>$2</i>");

	// Links [text](url)
	html = html.replace(
		/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
		'<a href="$2" target="_blank" rel="noopener">$1</a>'
	);

	// Lists (very lightweight)
	html = html.replace(/(^|\n)((?:\s*[-*]\s+[^\n]+(?:\n|$))+)/g, (_, lead, block) => {
		const items = block
			.trim()
			.split(/\n/)
			.map((l) => l.replace(/^\s*[-*]\s+/, "").trim())
			.filter(Boolean)
			.map((i) => `<li>${i}</li>`)
			.join("");
		return `${lead}<ul>${items}</ul>`;
	});
	html = html.replace(/(^|\n)((?:\s*\d+\.\s+[^\n]+(?:\n|$))+)/g, (_, lead, block) => {
		const items = block
			.trim()
			.split(/\n/)
			.map((l) => l.replace(/^\s*\d+\.\s+/, "").trim())
			.filter(Boolean)
			.map((i) => `<li>${i}</li>`)
			.join("");
		return `${lead}<ol>${items}</ol>`;
	});

	// Newlines → <br> (but not inside lists/tables we already produced)
	html = html.replace(/\n{2,}/g, "<br><br>").replace(/\n/g, "<br>");
	// Don't put <br>s right after block elements
	html = html.replace(/<\/(h\d|ul|ol|table|pre)><br>(<br>)?/g, "</$1>");

	// Re-inject inline codes
	html = html.replace(/\u0000INLINECODE(\d+)\u0000/g, (_, i) => {
		return `<code>${frappe.utils.escape_html(inlineCodes[+i])}</code>`;
	});
	// Re-inject code blocks
	html = html.replace(/\u0000CODEBLOCK(\d+)\u0000/g, (_, i) => {
		const b = codeBlocks[+i];
		return `<pre data-lang="${frappe.utils.escape_html(
			b.lang || ""
		)}"><code>${frappe.utils.escape_html(b.code)}</code></pre>`;
	});
	return html;
};

function renderMdTable(tbl) {
	const lines = tbl.trim().split(/\n/);
	if (lines.length < 2) return frappe.utils.escape_html(tbl);
	const head = splitRow(lines[0]);
	const rows = lines.slice(2).map(splitRow).filter((r) => r.length);
	const th = head.map((c) => `<th>${frappe.utils.escape_html(c)}</th>`).join("");
	const tr = rows
		.map(
			(r) =>
				`<tr>${r
					.map((c) => `<td>${frappe.utils.escape_html(c)}</td>`)
					.join("")}</tr>`
		)
		.join("");
	return `<table class="appe-buddy-md-table"><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
}

function splitRow(line) {
	return line
		.replace(/^\||\|$/g, "")
		.split("|")
		.map((c) => c.trim());
}

// ===========================================================================
// Tool result table renderer
// ===========================================================================

appe.buddy.renderToolResultTable = function (result) {
	if (!result || typeof result !== "object") return "";
	const r = result.result || result;

	// Find the first array-of-objects in the result (rows / customers / items / ...)
	let rows = null;
	let label = null;
	if (Array.isArray(r)) {
		rows = r;
	} else {
		for (const k of Object.keys(r)) {
			if (Array.isArray(r[k]) && r[k].length && typeof r[k][0] === "object") {
				rows = r[k];
				label = k;
				break;
			}
		}
	}
	if (!rows || !rows.length) return "";

	const cols = Object.keys(rows[0]).slice(0, 8); // cap columns for readability
	const max_rows = 20;
	const slice = rows.slice(0, max_rows);
	const th = cols
		.map(
			(c) =>
				`<th>${frappe.utils.escape_html(c.replace(/_/g, " "))}</th>`
		)
		.join("");
	const tr = slice
		.map(
			(row) =>
				`<tr>${cols
					.map((c) => {
						let v = row[c];
						if (v && typeof v === "object") v = JSON.stringify(v);
						if (typeof v === "number") {
							return `<td class="text-right">${frappe.utils.escape_html(
								String(v)
							)}</td>`;
						}
						return `<td>${frappe.utils.escape_html(v == null ? "" : String(v))}</td>`;
					})
					.join("")}</tr>`
		)
		.join("");
	const trunc =
		rows.length > max_rows
			? `<div class="text-muted small">${__(
					"Showing first {0} of {1} rows.",
					[max_rows, rows.length]
			  )}</div>`
			: "";
	const caption = label
		? `<div class="text-muted small mb-1">${frappe.utils.escape_html(label)}</div>`
		: "";
	return `<div class="appe-buddy-result-table">${caption}<div class="table-responsive"><table class="table table-sm table-bordered">
		<thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>${trunc}</div>`;
};

// ===========================================================================
// Date grouping
// ===========================================================================

function dateBucket(modified) {
	if (!modified) return "Older";
	const d = frappe.datetime.str_to_obj(modified);
	if (!d) return "Older";
	const now = new Date();
	const diff = Math.floor((now - d) / 86400000);
	if (diff < 1 && d.getDate() === now.getDate()) return __("Today");
	if (diff < 2 && now.getDate() - d.getDate() === 1) return __("Yesterday");
	if (diff < 7) return __("This Week");
	if (diff < 30) return __("Earlier this Month");
	return __("Older");
}

// ===========================================================================
// Chat UI
// ===========================================================================

appe.buddy.ChatUI = class ChatUI {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body).empty();
		// Add page-wrapper class so our CSS can collapse outer padding for a
		// fuller chat experience.
		$(page.body).closest(".page-container, .layout-main-section, .page-content")
			.addClass("appe-buddy-page-wrapper");
		this.conversations = [];
		this.current = null;
		this.sending = false;
		this.capabilities = {};
		this.last_user_message = null;
		this.boot_done = false;
		this.search_text = "";
	}

	render() {
		this.$body.html(`
			<div class="appe-buddy-shell">
				<aside class="appe-buddy-sidebar">
					<div class="appe-buddy-sidebar-head">
						<button class="btn btn-primary btn-sm appe-buddy-new-btn">
							<span class="fa fa-plus"></span> ${__("New Chat")}
						</button>
						<input type="search" class="form-control input-sm appe-buddy-search"
							placeholder="${__("Search chats…")}" style="margin-top:8px;">
					</div>
					<div class="appe-buddy-conv-list"></div>
				</aside>
				<main class="appe-buddy-main">
					
					<div class="appe-buddy-messages"></div>
					<form class="appe-buddy-input">
						<textarea
							rows="1"
							class="form-control appe-buddy-textarea"
							placeholder="${__("Ask Appe Buddy to query data, build a report, chart or DocType…")}"></textarea>
						<div class="appe-buddy-input-actions">
							<button type="button" class="btn btn-default btn-xs js-mic" title="${__("Voice input")}">
								<span class="fa fa-microphone"></span>
							</button>
							<button type="submit" class="btn btn-primary btn-sm appe-buddy-send-btn">
								<span class="fa fa-paper-plane"></span>
							</button>
						</div>
					</form>
					<div class="appe-buddy-foot text-muted small"></div>
				</main>
			</div>
		`);

		this.$sidebar = this.$body.find(".appe-buddy-conv-list");
		this.$search = this.$body.find(".appe-buddy-search");
		this.$messages = this.$body.find(".appe-buddy-messages");
		this.$textarea = this.$body.find(".appe-buddy-textarea");
		this.$send = this.$body.find(".appe-buddy-send-btn");
		this.$foot = this.$body.find(".appe-buddy-foot");
		this.$headerTitle = this.$body.find(".appe-buddy-header-title");
		this.$capabilities = this.$body.find(".appe-buddy-capabilities");
		this.$tokenBadge = this.$body.find(".appe-buddy-token-badge");
		this.$mic = this.$body.find(".js-mic");

		this.$body.find(".appe-buddy-new-btn").on("click", () => this.start_new_chat());
		this.$body.find(".appe-buddy-input").on("submit", (e) => {
			e.preventDefault();
			this.send_current();
		});
		this.$textarea
			.on("keydown", (e) => {
				if (e.key === "Enter" && !e.shiftKey) {
					e.preventDefault();
					this.send_current();
				}
			})
			.on("input", () => this.auto_resize_textarea());

		this.$search.on("input", (e) => {
			this.search_text = (e.target.value || "").toLowerCase();
			this.render_sidebar();
		});

		this.$body.find(".js-regen").on("click", () => this.regenerate());
		this.$body.find(".js-clear-ctx").on("click", () => this.clear_context());
		this.$body.find(".js-open-settings").on("click", () =>
			frappe.set_route("Form", "Appe Buddy Settings")
		);
		this.$mic.on("click", () => this.toggle_voice());

		this.page.set_secondary_action(__("Refresh"), () => this.load_conversations());
		this.page.set_indicator(__("Ready"), "green");

		this.maybe_load_initial();
	}

	maybe_load_initial() {
		if (this.boot_done) return;
		this.boot_done = true;
		this.boot();
	}

	async boot() {
		let meta = null;
		try {
			meta = await this.call("appe.ai.api.settings_public");
		} catch (e) {
			// settings_public failed — likely Buddy isn't configured at all
			this.render_disabled_state({ reason: "setup_needed", error: e.message });
			return;
		}
		if (!meta || !meta.enabled) {
			this.render_disabled_state({ reason: "disabled", meta });
			return;
		}

		this.capabilities = meta.capabilities || {};
		const caps = Object.entries(this.capabilities)
			.filter(([, v]) => v)
			.map(([k]) => k.replace(/_/g, " "))
			.join(" · ");
		this.$capabilities.text(
			__("{0} · {1} · {2}", [
				meta.provider || "—",
				meta.model || __("default model"),
				caps || __("read-only"),
			])
		);

		await this.load_conversations();
		if (!this.conversations.length) {
			this.show_empty_state();
		} else {
			this.open_conversation(this.conversations[0].name);
		}
	}

	render_disabled_state({ reason, error }) {
		this.$headerTitle.text("");
		this.$tokenBadge.text("");
		this.$capabilities.text(__("Appe Buddy is not active"));
		this.$body.find(".appe-buddy-input").hide();
		this.$body.find(".appe-buddy-header-right .btn").hide();
		this.$sidebar.html(
			`<div class="text-muted small p-3">${__("Appe Buddy is disabled.")}</div>`
		);

		const title =
			reason === "setup_needed"
				? __("Appe Buddy needs setup")
				: __("Appe Buddy is disabled");
		const body =
			reason === "setup_needed"
				? __(
						"It looks like Appe Buddy hasn't been configured yet. Add your API key and pick a provider in Appe Buddy Settings, then come back here."
				  )
				: __(
						"An administrator has disabled Appe Buddy. Open Appe Buddy Settings and toggle <b>Enable Appe Buddy</b> to start chatting."
				  );

		this.$messages.html(`
			<div class="appe-buddy-disabled-overlay">
				<div class="appe-buddy-disabled-card">
					<div class="appe-buddy-disabled-icon"><span class="fa fa-power-off"></span></div>
					<h3>${title}</h3>
					<p class="text-muted">${body}</p>
					${error ? `<div class="small text-danger">${frappe.utils.escape_html(error)}</div>` : ""}
					<div class="actions">
						<button class="btn btn-primary btn-sm js-open-settings-cta">
							<span class="fa fa-cog"></span> ${__("Open Appe Buddy Settings")}
						</button>
						<button class="btn btn-default btn-sm js-retry-boot">
							<span class="fa fa-refresh"></span> ${__("Retry")}
						</button>
					</div>
				</div>
			</div>
		`);
		this.$body.find(".js-open-settings-cta").on("click", () =>
			frappe.set_route("Form", "Appe Buddy Settings")
		);
		this.$body.find(".js-retry-boot").on("click", () => {
			this.boot_done = false;
			// Restore visibility of hidden controls
			this.$body.find(".appe-buddy-input").show();
			this.$body.find(".appe-buddy-header-right .btn").show();
			this.maybe_load_initial();
		});
	}

	async load_conversations() {
		this.$sidebar.html(`<div class="text-muted small p-3">${__("Loading…")}</div>`);
		try {
			this.conversations = await this.call("appe.ai.api.list_conversations", { limit: 200 });
		} catch (e) {
			this.conversations = [];
			this.$sidebar.html(
				`<div class="text-danger small p-3">${frappe.utils.escape_html(e.message || "Failed")}</div>`
			);
			return;
		}
		this.render_sidebar();
	}

	render_sidebar() {
		this.$sidebar.empty();
		const search = this.search_text || "";
		const filtered = this.conversations.filter((c) =>
			(c.title || "").toLowerCase().includes(search)
		);
		if (!filtered.length) {
			this.$sidebar.html(
				`<div class="text-muted small p-3">${
					this.conversations.length
						? __("No chats match your search.")
						: __("No chats yet. Click 'New Chat'.")
				}</div>`
			);
			return;
		}
		// Pinned first
		const pinned = filtered.filter((c) => c.pinned);
		const rest = filtered.filter((c) => !c.pinned);
		if (pinned.length) {
			this.append_sidebar_group(__("Pinned"), pinned);
		}
		// Group rest by date bucket
		const groups = {};
		rest.forEach((c) => {
			const k = dateBucket(c.modified);
			(groups[k] = groups[k] || []).push(c);
		});
		const order = [
			__("Today"),
			__("Yesterday"),
			__("This Week"),
			__("Earlier this Month"),
			__("Older"),
		];
		order.forEach((k) => {
			if (groups[k] && groups[k].length) this.append_sidebar_group(k, groups[k]);
		});
	}

	append_sidebar_group(label, list) {
		this.$sidebar.append(
			`<div class="appe-buddy-conv-group">${frappe.utils.escape_html(label)}</div>`
		);
		list.forEach((c) => this.$sidebar.append(this.build_conv_row(c)));
	}

	build_conv_row(c) {
		const $row = $(`
			<div class="appe-buddy-conv-row" data-name="${frappe.utils.escape_html(c.name)}">
				<div class="appe-buddy-conv-title">
					${c.pinned ? '<span class="fa fa-thumb-tack mr-1"></span>' : ""}
					${frappe.utils.escape_html(c.title || c.name)}
				</div>
				<div class="appe-buddy-conv-meta">
					${frappe.datetime.comment_when(c.modified)} · ${c.total_messages || 0} ${__("msgs")}
					${c.total_tokens ? ` · ${c.total_tokens} ${__("tok")}` : ""}
				</div>
				<div class="appe-buddy-conv-actions">
					<a class="text-muted js-rename" title="${__("Rename")}"><span class="fa fa-pencil"></span></a>
					<a class="text-muted js-pin" title="${__("Pin")}"><span class="fa fa-thumb-tack"></span></a>
					<a class="text-danger js-delete" title="${__("Delete")}"><span class="fa fa-trash"></span></a>
				</div>
			</div>
		`);
		$row.on("click", (e) => {
			if ($(e.target).closest(".appe-buddy-conv-actions").length) return;
			this.open_conversation(c.name);
		});
		$row.find(".js-rename").on("click", (e) => {
			e.stopPropagation();
			frappe.prompt(
				[{ fieldname: "title", label: __("Title"), fieldtype: "Data", default: c.title }],
				(values) =>
					this.call("appe.ai.api.rename_conversation", {
						name: c.name,
						title: values.title,
					}).then(() => this.load_conversations()),
				__("Rename Chat"),
				__("Save")
			);
		});
		$row.find(".js-pin").on("click", (e) => {
			e.stopPropagation();
			this.call("appe.ai.api.pin_conversation", {
				name: c.name,
				pinned: c.pinned ? 0 : 1,
			}).then(() => this.load_conversations());
		});
		$row.find(".js-delete").on("click", (e) => {
			e.stopPropagation();
			frappe.confirm(__("Delete this chat? This cannot be undone."), () =>
				this.call("appe.ai.api.delete_conversation", { name: c.name }).then(() => {
					if (this.current && this.current.name === c.name) {
						this.current = null;
						this.$messages.empty();
						this.show_empty_state();
					}
					this.load_conversations();
				})
			);
		});
		if (this.current && this.current.name === c.name) $row.addClass("active");
		return $row;
	}

	show_empty_state() {
		this.$headerTitle.text("");
		this.$tokenBadge.text("");
		this.$messages.html(`
			<div class="appe-buddy-empty">
				<div class="appe-buddy-empty-icon"><span class="fa fa-magic"></span></div>
				<h4>${__("Hi! I'm Appe Buddy")}</h4>
				<p class="text-muted">${__("I can read your Frappe & ERPNext data, build reports, charts, dashboards and even new DocTypes.")}</p>
				<div class="appe-buddy-suggestion-groups">
					${this.suggestion_groups()}
				</div>
			</div>
		`);
		this.$body.find(".appe-buddy-suggestion").on("click", (e) => {
			const text = $(e.currentTarget).attr("data-prompt") || $(e.currentTarget).text().trim();
			this.$textarea.val(text);
			this.$textarea.trigger("focus");
			this.auto_resize_textarea();
		});
	}

	suggestion_groups() {
		const groups = {
			"📊 Reports & Charts": [
				"Show me top 5 customers by sales this year",
				"Create a Dashboard Chart of monthly Sales Invoice totals",
				"Run the Profit and Loss Statement for last fiscal year",
				"Build a Number Card showing total outstanding amount",
			],
			"📦 Inventory": [
				"Stock balance for item 'ITEM-0001'",
				"Items with low stock in main warehouse",
				"Find item 'led bulb'",
			],
			"💰 Accounting": [
				"Outstanding invoices for our default company",
				"GL balance of 'Cash - Company' as of today",
				"Trial balance for current fiscal year",
			],
			"🛠 Build": [
				"Create a custom DocType 'Visitor Log' with name, mobile_no, purpose",
				"Create a Report listing all Sales Invoices grouped by customer",
				"Make a Dashboard combining sales chart + outstanding card",
			],
		};
		return Object.entries(groups)
			.map(
				([label, items]) => `
			<div class="appe-buddy-suggestion-group">
				<div class="appe-buddy-suggestion-title">${frappe.utils.escape_html(label)}</div>
				<div class="appe-buddy-suggestion-chips">
					${items
						.map(
							(t) => `<button class="btn btn-default btn-xs appe-buddy-suggestion"
								data-prompt="${frappe.utils.escape_html(t)}">${frappe.utils.escape_html(t)}</button>`
						)
						.join("")}
				</div>
			</div>
		`
			)
			.join("");
	}

	async start_new_chat() {
		try {
			const data = await this.call("appe.ai.api.new_conversation", {
				title: "New Chat",
				context: null,
			});
			await this.load_conversations();
			this.open_conversation(data.name);
		} catch (e) {
			frappe.show_alert({ message: e.message || "Failed", indicator: "red" });
		}
	}

	async open_conversation(name) {
		this.$messages.html(`<div class="text-muted small p-3">${__("Loading conversation…")}</div>`);
		try {
			this.current = await this.call("appe.ai.api.get_conversation", {
				name,
				message_limit: 300,
			});
		} catch (e) {
			this.$messages.html(
				`<div class="text-danger small p-3">${frappe.utils.escape_html(e.message || "Failed")}</div>`
			);
			return;
		}
		this.$headerTitle.text(this.current.title || name);
		this.$tokenBadge.text(
			this.current.total_tokens
				? `${this.current.total_tokens.toLocaleString()} ${__("tokens")}`
				: ""
		);
		this.render_messages();
		this.render_sidebar();
	}

	render_messages() {
		const msgs = (this.current && this.current.messages) || [];
		this.$messages.empty();
		if (!msgs.length) {
			this.$messages.html(
				`<div class="text-muted small p-3">${__("Send your first message to start.")}</div>`
			);
			return;
		}
		this.last_user_message = null;
		msgs.forEach((m) => {
			if (m.role === "user") this.last_user_message = m.content;
			this.append_message_dom(m);
		});
		this.scroll_bottom();
	}

	append_message_dom(m) {
		const role = m.role;
		if (role === "system") return;
		if (role === "tool") {
			const $row = $(`
				<div class="appe-buddy-msg appe-buddy-msg-tool">
					<div class="appe-buddy-tool-line">
						<span class="appe-buddy-tool-chip">
							<span class="fa fa-cogs"></span>
							${frappe.utils.escape_html(m.tool_name || "tool")}
						</span>
						<span class="appe-buddy-tool-summary text-muted small">${this.summarize_tool_result(m)}</span>
					</div>
				</div>
			`);
			const tableHtml = m.tool_result && appe.buddy.renderToolResultTable(m.tool_result);
			if (tableHtml) $row.append(tableHtml);
			// Collapsible raw JSON
			if (m.tool_result) {
				$row.append(`
					<details class="appe-buddy-tool-raw">
						<summary class="text-muted small">${__("raw json")}</summary>
						<pre>${frappe.utils.escape_html(JSON.stringify(m.tool_result, null, 2))}</pre>
					</details>
				`);
			}
			this.$messages.append($row);
			return;
		}
		if (role === "assistant" && m.tool_name) {
			const argText = (() => {
				try {
					return JSON.stringify(m.tool_arguments || {}, null, 2);
				} catch {
					return String(m.tool_arguments || "");
				}
			})();
			const $row = $(`
				<div class="appe-buddy-msg appe-buddy-msg-assistant">
					<span class="appe-buddy-tool-chip">
						<span class="fa fa-bolt"></span>
						${__("Calling")} <b>${frappe.utils.escape_html(m.tool_name)}</b>
					</span>
					<details class="appe-buddy-tool-args">
						<summary class="text-muted small">${__("arguments")}</summary>
						<pre>${frappe.utils.escape_html(argText)}</pre>
					</details>
				</div>
			`);
			this.$messages.append($row);
			return;
		}
		const $row = $(`
			<div class="appe-buddy-msg appe-buddy-msg-${role}">
				<div class="appe-buddy-msg-bubble">${appe.buddy.renderMarkdown(m.content || "")}</div>
				<div class="appe-buddy-msg-meta">
					<span>${frappe.datetime.comment_when(m.created_at) || ""}</span>
					${
						role === "assistant"
							? `<a class="js-copy text-muted ml-2" title="${__("Copy")}">
									<span class="fa fa-clone"></span>
								</a>`
							: ""
					}
				</div>
			</div>
		`);
		$row.find(".js-copy").on("click", (e) => {
			e.preventDefault();
			frappe.utils.copy_to_clipboard(m.content || "");
			frappe.show_alert({ message: __("Copied"), indicator: "green" });
		});
		this.$messages.append($row);
	}

	summarize_tool_result(m) {
		const r = m.tool_result;
		if (!r) return __("done");
		if (typeof r === "object") {
			if (r.ok === false) {
				return `<span class="text-danger">${frappe.utils.escape_html(r.error || "error")}</span>`;
			}
			const result = r.result || r;
			const keys = Object.keys(result || {});
			const preview = keys.slice(0, 4).map((k) => {
				const v = result[k];
				if (Array.isArray(v)) return `${k}: ${v.length} items`;
				if (typeof v === "object" && v !== null) return `${k}: { … }`;
				return `${k}: ${String(v).slice(0, 40)}`;
			});
			return frappe.utils.escape_html(preview.join(" · ") || "ok");
		}
		return frappe.utils.escape_html(String(r).slice(0, 200));
	}

	scroll_bottom() {
		const el = this.$messages[0];
		if (el) el.scrollTop = el.scrollHeight;
	}

	auto_resize_textarea() {
		const el = this.$textarea[0];
		if (!el) return;
		el.style.height = "auto";
		el.style.height = Math.min(el.scrollHeight, 200) + "px";
	}

	async send_current(prefill_message) {
		const text = (prefill_message != null ? prefill_message : this.$textarea.val() || "").trim();
		if (!text || this.sending) return;
		if (!this.current) {
			await this.start_new_chat();
			if (!this.current) return;
		}
		this.sending = true;
		this.$send.prop("disabled", true).find(".fa").removeClass("fa-paper-plane").addClass("fa-spinner fa-spin");

		this.append_message_dom({
			role: "user",
			content: text,
			created_at: frappe.datetime.now_datetime(),
		});
		if (prefill_message == null) this.$textarea.val("");
		this.auto_resize_textarea();
		this.scroll_bottom();
		const $thinking = $(`
			<div class="appe-buddy-msg appe-buddy-msg-assistant appe-buddy-thinking">
				<div class="appe-buddy-msg-bubble">
					<span class="fa fa-circle-notch fa-spin"></span> ${__("thinking…")}
				</div>
			</div>
		`);
		this.$messages.append($thinking);
		this.scroll_bottom();

		try {
			const data = await this.call("appe.ai.api.send_message", {
				message: text,
				conversation: this.current.name,
				context: this.build_context(),
			});
			$thinking.remove();
			await this.open_conversation(data.conversation);
			await this.load_conversations();
		} catch (e) {
			$thinking.remove();
			this.append_message_dom({
				role: "assistant",
				content: "**Error:** " + (e.message || "Failed"),
				created_at: frappe.datetime.now_datetime(),
			});
			this.scroll_bottom();
		} finally {
			this.sending = false;
			this.$send.prop("disabled", false).find(".fa").removeClass("fa-spinner fa-spin").addClass("fa-paper-plane");
		}
	}

	async regenerate() {
		if (!this.last_user_message) {
			frappe.show_alert({ message: __("Nothing to regenerate"), indicator: "blue" });
			return;
		}
		this.send_current(this.last_user_message);
	}

	clear_context() {
		this.$textarea.val("").trigger("focus");
		this.auto_resize_textarea();
	}

	build_context() {
		return { source: "desk_page", route: window.location.hash || "" };
	}

	// --- Voice input via Web Speech API ---
	toggle_voice() {
		const W = window;
		const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
		if (!SR) {
			frappe.show_alert({
				message: __("Voice input is not supported in this browser."),
				indicator: "orange",
			});
			return;
		}
		if (this._sr) {
			this._sr.stop();
			this._sr = null;
			this.$mic.removeClass("recording");
			return;
		}
		const sr = new SR();
		sr.continuous = false;
		sr.interimResults = true;
		sr.lang = frappe.boot.lang || "en-IN";
		sr.onresult = (e) => {
			let txt = "";
			for (let i = e.resultIndex; i < e.results.length; ++i) {
				txt += e.results[i][0].transcript;
			}
			this.$textarea.val(txt);
			this.auto_resize_textarea();
		};
		sr.onerror = () => {
			this.$mic.removeClass("recording");
		};
		sr.onend = () => {
			this.$mic.removeClass("recording");
			this._sr = null;
		};
		sr.start();
		this._sr = sr;
		this.$mic.addClass("recording");
	}

	async call(method, args = {}) {
		const isPost =
			method.indexOf("send_") !== -1 ||
			method.indexOf("new_") !== -1 ||
			method.indexOf("rename_") !== -1 ||
			method.indexOf("pin_") !== -1 ||
			method.indexOf("archive_") !== -1 ||
			method.indexOf("delete_") !== -1;
		return new Promise((resolve, reject) => {
			frappe.call({
				method,
				args,
				type: isPost ? "POST" : "GET",
				callback: (r) => {
					if (r.message && r.message.status === false) {
						reject(new Error(r.message.error || "Failed"));
					} else if (r.message && r.message.data !== undefined) {
						resolve(r.message.data);
					} else if (r.message) {
						resolve(r.message);
					} else {
						resolve(null);
					}
				},
				error: (err) => reject(new Error(err.message || "Network error")),
			});
		});
	}
};
