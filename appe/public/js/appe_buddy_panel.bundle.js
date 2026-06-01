// Appe Buddy floating side panel.
// Loaded on every Desk page via app_include_js. Adds a circular FAB at the
// bottom-right that opens a slide-in panel. The panel auto-attaches the
// current Desk page (route, doctype, docname) to each message as `context`
// so the AI has accurate, data-aware grounding.

frappe.provide("appe.buddy");

(function () {
	"use strict";

	const PANEL_ID = "appe-buddy-floating-drawer";
	const FAB_ID = "appe-buddy-floating-fab";

	// Cached enabled flag so we don't spam settings_public on every route change.
	// Re-fetched on init, on every Settings save and every 60s.
	let _last_enabled = null;
	let _last_check_at = 0;
	const RECHECK_MS = 60 * 1000;

	function init() {
		if (!window.frappe || !frappe.session || frappe.session.user === "Guest") return;
		if (document.getElementById(FAB_ID)) return;
		// Always mount but force-hide (inline style + class) until we confirm
		// `enabled=1` from the server. This prevents the FAB from flashing on
		// when CSS hasn't loaded yet or when Buddy is disabled.
		mount();
		hide_fab();
		fetch_settings_and_toggle({ force: true });

		// Re-check on every route change so toggling Settings reflects right away.
		if (window.frappe && frappe.router && frappe.router.on) {
			frappe.router.on("change", () => fetch_settings_and_toggle({ throttle: true }));
		}

		// Re-check after any successful Appe Buddy Settings save (same tab).
		$(document).on("appe-buddy-settings-saved", () =>
			fetch_settings_and_toggle({ force: true })
		);

		// Listen for realtime updates if/when the server emits one.
		if (window.frappe && frappe.realtime && frappe.realtime.on) {
			frappe.realtime.on("appe_buddy_settings_changed", () =>
				fetch_settings_and_toggle({ force: true })
			);
		}

		// Safety net polling — very light, every minute.
		setInterval(() => fetch_settings_and_toggle({}), RECHECK_MS);
	}

	function hide_fab() {
		const fab = document.getElementById(FAB_ID);
		if (fab) {
			fab.classList.add("hidden");
			fab.style.display = "none";
		}
		const drawer = document.getElementById(PANEL_ID);
		if (drawer) drawer.classList.remove("open");
	}

	function show_fab() {
		const fab = document.getElementById(FAB_ID);
		if (fab) {
			fab.classList.remove("hidden");
			fab.style.display = "";
		}
	}

	function apply_enabled(enabled) {
		_last_enabled = !!enabled;
		_last_check_at = Date.now();
		if (_last_enabled) show_fab();
		else hide_fab();
	}

	function fetch_settings_and_toggle({ force = false, throttle = false } = {}) {
		const now = Date.now();
		if (throttle && !force && now - _last_check_at < 5000) return; // de-dupe rapid route changes
		if (!window.frappe || !frappe.call) return hide_fab();
		try {
			frappe.call({
				method: "appe.ai.api.settings_public",
				type: "GET",
				callback: (r) => {
					const data = (r && r.message && r.message.data) || (r && r.message) || {};
					apply_enabled(!!data.enabled);
				},
				error: () => apply_enabled(false),
				freeze: false,
			});
		} catch (e) {
			apply_enabled(false);
		}
	}

	function mount() {
		const fab = document.createElement("button");
		fab.id = FAB_ID;
		fab.className = "appe-buddy-fab hidden";
		fab.style.display = "none"; // hard-hidden until we confirm enabled=1
		fab.title = __("Open Appe Buddy");
		fab.innerHTML = '<span class="fa fa-magic"></span>';
		document.body.appendChild(fab);

		const drawer = document.createElement("div");
		drawer.id = PANEL_ID;
		drawer.className = "appe-buddy-drawer";
		drawer.innerHTML = `
			<div class="appe-buddy-drawer-head">
				<div>
					<span class="title">${__("Appe Buddy")}</span>
					<span class="ctx-chip context-chip">${__("Desk")}</span>
				</div>
				<div>
					<a class="js-open-page" title="${__("Open full page")}">
						<span class="fa fa-expand"></span>
					</a>
					<a class="js-new-chat" title="${__("New Chat")}">
						<span class="fa fa-plus"></span>
					</a>
					<a class="js-close" title="${__("Close")}">
						<span class="fa fa-times"></span>
					</a>
				</div>
			</div>
			<div class="appe-buddy-drawer-body">
				<div class="appe-buddy-messages"></div>
				<form class="appe-buddy-input">
					<textarea
						rows="2"
						class="form-control appe-buddy-textarea"
						placeholder="${__("Ask about this screen…")}"></textarea>
					<button type="submit" class="btn btn-primary appe-buddy-send-btn">
						<span class="fa fa-paper-plane"></span>
					</button>
				</form>
			</div>
		`;
		document.body.appendChild(drawer);

		const panel = new appe.buddy.FloatingPanel(drawer);
		fab.addEventListener("click", () => panel.toggle());
		drawer.querySelector(".js-close").addEventListener("click", () => panel.close());
		drawer.querySelector(".js-new-chat").addEventListener("click", () => panel.new_chat());
		drawer.querySelector(".js-open-page").addEventListener("click", () => {
			panel.close();
			frappe.set_route("appe-buddy");
		});
		drawer.querySelector(".appe-buddy-input").addEventListener("submit", (e) => {
			e.preventDefault();
			panel.send_current();
		});
		drawer.querySelector(".appe-buddy-textarea").addEventListener("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				panel.send_current();
			}
		});

		window.appe.buddy.floating_panel = panel;
		// React to route changes so the context chip reflects the current page
		const update_chip = () => panel.update_context_chip();
		$(document).on("page-change", update_chip);
		$(document).on("form-refresh", update_chip);
		update_chip();
	}

	appe.buddy.FloatingPanel = class FloatingPanel {
		constructor(root) {
			this.root = root;
			this.$drawer = $(root);
			this.$messages = this.$drawer.find(".appe-buddy-messages");
			this.$textarea = this.$drawer.find(".appe-buddy-textarea");
			this.$send = this.$drawer.find(".appe-buddy-send-btn");
			this.$chip = this.$drawer.find(".context-chip");
			this.conversation = null;
			this.sending = false;
			this.opened_once = false;
		}

		open() {
			this.$drawer.addClass("open");
			if (!this.opened_once) {
				this.opened_once = true;
				this.bootstrap();
			}
			this.update_context_chip();
			setTimeout(() => this.$textarea.trigger("focus"), 250);
		}

		close() {
			this.$drawer.removeClass("open");
		}

		toggle() {
			if (this.$drawer.hasClass("open")) this.close();
			else this.open();
		}

		async bootstrap() {
			// Try to resume the most recent active conversation, otherwise start a new one
			try {
				const list = await this.call("appe.ai.api.list_conversations", {
					limit: 1,
					status: "Active",
				});
				if (Array.isArray(list) && list.length) {
					this.conversation = list[0].name;
					const data = await this.call("appe.ai.api.get_conversation", {
						name: list[0].name,
						message_limit: 50,
					});
					this.render_messages(data.messages || []);
					return;
				}
			} catch (e) {
				// fall through
			}
			this.render_empty();
		}

		render_empty() {
			this.$messages.html(`
				<div class="appe-buddy-empty" style="padding:18px 8px;">
					<div class="appe-buddy-empty-icon"><span class="fa fa-magic"></span></div>
					<div class="text-muted small">${__("I see your current screen as context.")}</div>
					<div class="appe-buddy-suggestions" style="margin-top:10px;">
						<button class="btn btn-default btn-xs appe-buddy-suggestion">${__("Summarize this record")}</button>
						<button class="btn btn-default btn-xs appe-buddy-suggestion">${__("Explain what this DocType is for")}</button>
						<button class="btn btn-default btn-xs appe-buddy-suggestion">${__("Suggest 3 improvements")}</button>
					</div>
				</div>
			`);
			this.$drawer.find(".appe-buddy-suggestion").on("click", (e) => {
				this.$textarea.val($(e.currentTarget).text().trim()).trigger("focus");
			});
		}

		render_messages(msgs) {
			this.$messages.empty();
			(msgs || []).forEach((m) => this.append_message_dom(m));
			this.scroll_bottom();
		}

		append_message_dom(m) {
			const role = m.role;
			if (role === "system") return;
			if (role === "tool") {
				const summary = this.summarize_tool_result(m);
				const row = $(`
					<div class="appe-buddy-msg appe-buddy-msg-tool">
						<span class="appe-buddy-tool-chip">
							<span class="fa fa-cogs"></span>
							${frappe.utils.escape_html(m.tool_name || "tool")}
						</span>
						<span class="appe-buddy-tool-summary text-muted small">${summary}</span>
					</div>
				`);
				this.$messages.append(row);
				return;
			}
			if (role === "assistant" && m.tool_name) {
				const row = $(`
					<div class="appe-buddy-msg appe-buddy-msg-assistant">
						<span class="appe-buddy-tool-chip">
							<span class="fa fa-bolt"></span>
							${__("Calling")} <b>${frappe.utils.escape_html(m.tool_name)}</b>
						</span>
					</div>
				`);
				this.$messages.append(row);
				return;
			}
			const row = $(`
				<div class="appe-buddy-msg appe-buddy-msg-${role}">
					<div class="appe-buddy-msg-bubble">${this.format_text(m.content || "")}</div>
				</div>
			`);
			this.$messages.append(row);
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
				const preview = keys.slice(0, 3).map((k) => {
					const v = result[k];
					if (Array.isArray(v)) return `${k}: ${v.length}`;
					if (typeof v === "object" && v !== null) return `${k}: {…}`;
					return `${k}: ${String(v).slice(0, 24)}`;
				});
				return frappe.utils.escape_html(preview.join(" · ") || "ok");
			}
			return frappe.utils.escape_html(String(r).slice(0, 140));
		}

		format_text(text) {
			const escaped = frappe.utils.escape_html(text);
			return escaped
				.replace(/```([\s\S]*?)```/g, (_, code) => `<pre>${code}</pre>`)
				.replace(/`([^`]+)`/g, "<code>$1</code>")
				.replace(/\n/g, "<br>");
		}

		scroll_bottom() {
			const el = this.$messages[0];
			if (el) el.scrollTop = el.scrollHeight;
		}

		current_context() {
			const ctx = {
				source: "floating_panel",
				route: (frappe.get_route && frappe.get_route().join("/")) || window.location.hash,
			};
			try {
				const route = frappe.get_route ? frappe.get_route() : [];
				if (route[0] === "Form" && route[1]) {
					ctx.doctype = route[1];
					if (route[2]) ctx.docname = route[2];
					if (cur_frm && cur_frm.doc) {
						const d = cur_frm.doc;
						ctx.doctype = d.doctype || ctx.doctype;
						ctx.docname = d.name || ctx.docname;
						// Send a tiny snapshot of key fields (no children, no long text)
						ctx.doc_snapshot = {};
						const meta = cur_frm.meta || {};
						(meta.fields || []).forEach((f) => {
							if (
								[
									"Section Break",
									"Column Break",
									"Tab Break",
									"HTML",
									"Table",
									"Table MultiSelect",
									"Long Text",
									"Text Editor",
									"Markdown Editor",
									"HTML Editor",
									"Code",
									"Signature",
									"Attach",
									"Attach Image",
									"Password",
								].indexOf(f.fieldtype) === -1
							) {
								const val = d[f.fieldname];
								if (val !== undefined && val !== null && val !== "") {
									ctx.doc_snapshot[f.fieldname] = val;
								}
							}
						});
					}
				} else if (route[0] === "List" && route[1]) {
					ctx.doctype = route[1];
					ctx.list_view = true;
				} else if (route[0] === "query-report" && route[1]) {
					ctx.report = route[1];
				} else if (route[0] === "dashboard-view" && route[1]) {
					ctx.dashboard = route[1];
				}
			} catch (e) {
				// best-effort, ignore
			}
			return ctx;
		}

		update_context_chip() {
			const ctx = this.current_context();
			let label = __("Desk");
			if (ctx.doctype && ctx.docname) label = `${ctx.doctype} · ${ctx.docname}`;
			else if (ctx.doctype) label = ctx.doctype;
			else if (ctx.report) label = `Report · ${ctx.report}`;
			else if (ctx.dashboard) label = `Dashboard · ${ctx.dashboard}`;
			this.$chip.text(label);
		}

		async new_chat() {
			try {
				const data = await this.call("appe.ai.api.new_conversation", {
					title: "Quick chat",
					context: this.current_context(),
				});
				this.conversation = data.name;
				this.render_empty();
			} catch (e) {
				frappe.show_alert({ message: e.message || "Failed", indicator: "red" });
			}
		}

		async send_current() {
			const text = (this.$textarea.val() || "").trim();
			if (!text || this.sending) return;
			this.sending = true;
			this.$send
				.prop("disabled", true)
				.find(".fa")
				.removeClass("fa-paper-plane")
				.addClass("fa-spinner fa-spin");

			this.append_message_dom({ role: "user", content: text });
			this.$textarea.val("");
			this.scroll_bottom();
			const $thinking = $(`
				<div class="appe-buddy-msg appe-buddy-msg-assistant appe-buddy-thinking">
					<div class="appe-buddy-msg-bubble"><span class="fa fa-circle-notch fa-spin"></span> ${__("thinking…")}</div>
				</div>
			`);
			this.$messages.append($thinking);
			this.scroll_bottom();

			try {
				const data = await this.call("appe.ai.api.send_message", {
					message: text,
					conversation: this.conversation || null,
					context: this.current_context(),
				});
				this.conversation = data.conversation;
				$thinking.remove();
				// Refetch the canonical history (includes tool calls/results)
				const conv = await this.call("appe.ai.api.get_conversation", {
					name: data.conversation,
					message_limit: 100,
				});
				this.render_messages(conv.messages || []);
			} catch (e) {
				$thinking.remove();
				this.append_message_dom({
					role: "assistant",
					content: "**Error:** " + (e.message || "Failed"),
				});
				this.scroll_bottom();
			} finally {
				this.sending = false;
				this.$send
					.prop("disabled", false)
					.find(".fa")
					.removeClass("fa-spinner fa-spin")
					.addClass("fa-paper-plane");
			}
		}

		call(method, args = {}) {
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

	// Boot when Frappe is ready
	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", () => $(document).ready(init));
	} else {
		$(document).ready(init);
	}
})();
