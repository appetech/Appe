// Copyright (c) 2026, Appe Technologies and contributors
// For license information, please see license.txt

frappe.provide("appe.buddy_settings");

const PROVIDER_DEFAULTS = {
	OpenAI: { model: "gpt-4o-mini", api_base_url: "https://api.openai.com/v1" },
	"OpenAI Compatible": { model: "gpt-4o-mini", api_base_url: "" },
	Anthropic: {
		model: "claude-3-5-sonnet-20241022",
		api_base_url: "https://api.anthropic.com/v1",
	},
	Gemini: {
		model: "gemini-2.5-flash",
		api_base_url: "https://generativelanguage.googleapis.com/v1beta",
	},
};

frappe.ui.form.on("Appe Buddy Settings", {
	refresh(frm) {
		add_actions(frm);
		render_stats(frm);
		hint_default_model(frm);
		hydrate_model_options(frm);
	},

	after_save(frm) {
		// Notify floating panel + any other listeners that settings changed.
		// Panel re-fetches `settings_public` and shows/hides the FAB instantly.
		$(document).trigger("appe-buddy-settings-saved", [
			{ enabled: !!frm.doc.enabled },
		]);
	},

	provider(frm) {
		const preset = PROVIDER_DEFAULTS[frm.doc.provider];
		if (!preset) return;
		// If model is blank → suggest the preset default
		if (!frm.doc.model) frm.set_value("model", preset.model);
		// If base URL is blank → suggest the preset URL
		if (!frm.doc.api_base_url && preset.api_base_url) {
			frm.set_value("api_base_url", preset.api_base_url);
		}
		hydrate_model_options(frm);
		hint_default_model(frm);
	},

	model(frm) {
		hint_default_model(frm);
	},
});

function add_actions(frm) {
	frm.add_custom_button(__("Test Connection"), () => {
		frappe.call({
			method: "appe.ai.api.test_connection",
			freeze: true,
			freeze_message: __("Talking to AI provider..."),
			callback: (r) => {
				if (r.message && r.message.ok) {
					frappe.msgprint({
						title: __("Appe Buddy"),
						indicator: "green",
						message: __("Connection OK. Provider: {0}, Model: {1}", [
							r.message.provider,
							r.message.model,
						]),
					});
				} else {
					frappe.msgprint({
						title: __("Appe Buddy"),
						indicator: "red",
						message: (r.message && r.message.error) || __("Unknown error"),
					});
				}
			},
		});
	});

	frm.add_custom_button(__("Browse Models"), () => browse_models(frm));

	frm.add_custom_button(__("Open Appe Buddy"), () => frappe.set_route("appe-buddy"));

	frm.add_custom_button(
		__("Reset to Provider Defaults"),
		() => {
			const preset = PROVIDER_DEFAULTS[frm.doc.provider || "OpenAI"];
			if (!preset) return;
			frappe.confirm(
				__(
					"Reset model and API base URL to defaults for {0}? Your API key will not be touched.",
					[frm.doc.provider || "OpenAI"]
				),
				() => {
					frm.set_value("model", preset.model);
					frm.set_value("api_base_url", preset.api_base_url);
					frm.save();
				}
			);
		},
		__("Actions")
	);

	frm.add_custom_button(
		__("Refresh Stats"),
		() => render_stats(frm, /*force*/ true),
		__("Actions")
	);
}

function hint_default_model(frm) {
	const preset = PROVIDER_DEFAULTS[frm.doc.provider] || PROVIDER_DEFAULTS.OpenAI;
	if (!frm.doc.model) {
		frm.set_df_property(
			"model",
			"description",
			__("Will default to <b>{0}</b> when you save.", [preset.model])
		);
	} else {
		frm.set_df_property(
			"model",
			"description",
			__("Default for {0} is {1}. Leave blank to auto-use the default.", [
				frm.doc.provider || "OpenAI",
				preset.model,
			])
		);
	}
	frm.refresh_field("model");
}

function hydrate_model_options(frm) {
	const preset = PROVIDER_DEFAULTS[frm.doc.provider] || PROVIDER_DEFAULTS.OpenAI;
	frappe.call({
		method:
			"appe.appe.doctype.appe_buddy_settings.appe_buddy_settings.get_provider_preset",
		args: { provider: frm.doc.provider || "OpenAI" },
		callback: (r) => {
			const models = (r.message && r.message.models) || [preset.model];
			const df = frm.fields_dict.model && frm.fields_dict.model.df;
			if (df) {
				df.options = models.join("\n");
				frm.refresh_field("model");
			}
		},
	});
}

function browse_models(frm) {
	if (!frm.doc.api_key && !frm.doc.__unsaved) {
		frappe.msgprint(__("Save the API key first to fetch a live model list."));
	}
	const dlg = new frappe.ui.Dialog({
		title: __("Browse Models"),
		fields: [
			{ fieldname: "html", fieldtype: "HTML" },
		],
	});
	dlg.show();
	dlg.fields_dict.html.$wrapper.html(
		`<div class="text-muted small">${__("Loading models from {0}…", [frm.doc.provider])}</div>`
	);
	frappe.call({
		method:
			"appe.appe.doctype.appe_buddy_settings.appe_buddy_settings.list_provider_models",
		args: { provider: frm.doc.provider },
		callback: (r) => {
			const data = r.message || {};
			const list = data.models || [];
			if (!list.length) {
				dlg.fields_dict.html.$wrapper.html(
					`<div class="text-danger">${__("No models found.")}</div>`
				);
				return;
			}
			const source = data.source === "live" ? __("Live from provider") : __("Curated defaults");
			const hint = data.hint
				? `<div class="text-muted small mb-2">${frappe.utils.escape_html(data.hint)}</div>`
				: "";
			const items = list
				.map(
					(m) => `
				<button class="btn btn-default btn-sm appe-buddy-model-pick" data-model="${frappe.utils.escape_html(m)}">
					${frappe.utils.escape_html(m)}
				</button>
			`
				)
				.join(" ");
			dlg.fields_dict.html.$wrapper.html(`
				<div class="text-muted small mb-2">${__("Source")}: ${source}</div>
				${hint}
				<div class="appe-buddy-model-grid">${items}</div>
			`);
			dlg.fields_dict.html.$wrapper.find(".appe-buddy-model-pick").on("click", function () {
				const m = $(this).data("model");
				frm.set_value("model", m);
				frm.save();
				dlg.hide();
			});
		},
	});
}

function render_stats(frm, force = false) {
	if (!frm.fields_dict.section_safety) return;
	let $host = frm.$wrapper.find(".appe-buddy-stats-panel");
	if ($host.length && !force) return;
	if (!$host.length) {
		$host = $(
			`<div class="appe-buddy-stats-panel" style="padding: 12px 0 0 0;"></div>`
		);
		// Insert just above the safety section
		const $safety = frm.fields_dict.section_safety.wrapper
			? $(frm.fields_dict.section_safety.wrapper)
			: null;
		if ($safety && $safety.length) {
			$safety.before($host);
		} else {
			frm.$wrapper.find(".form-layout").append($host);
		}
	}
	$host.html(`<div class="text-muted small">${__("Loading stats…")}</div>`);

	frappe.call({
		method: "appe.appe.doctype.appe_buddy_settings.appe_buddy_settings.get_stats",
		callback: (r) => {
			const data = r.message || {};
			const t = data.totals || {};
			const tool_rows = (data.tool_usage || [])
				.map(
					(x) => `
				<tr>
					<td>${frappe.utils.escape_html(x.tool_name || "")}</td>
					<td class="text-right">${x.calls || 0}</td>
					<td class="text-right text-success">${x.success || 0}</td>
					<td class="text-right text-danger">${(x.errors || 0) + (x.blocked || 0)}</td>
					<td class="text-right text-muted">${x.avg_ms || 0} ms</td>
				</tr>
			`
				)
				.join("");
			const user_rows = (data.top_users || [])
				.map(
					(x) => `
				<tr>
					<td>${frappe.utils.escape_html(x.user || "")}</td>
					<td class="text-right">${x.conversations || 0}</td>
					<td class="text-right text-muted">${x.tokens || 0}</td>
				</tr>
			`
				)
				.join("");

			const last_used = t.last_used
				? frappe.datetime.comment_when(t.last_used)
				: __("never");

			$host.html(`
				<div class="appe-buddy-stats-grid">
					<div class="card stats-card">
						<div class="stats-label">${__("Conversations")}</div>
						<div class="stats-value">${t.conversations || 0}</div>
					</div>
					<div class="card stats-card">
						<div class="stats-label">${__("Messages")}</div>
						<div class="stats-value">${t.messages || 0}</div>
					</div>
					<div class="card stats-card">
						<div class="stats-label">${__("Tokens used")}</div>
						<div class="stats-value">${t.tokens || 0}</div>
					</div>
					<div class="card stats-card">
						<div class="stats-label">${__("Last activity")}</div>
						<div class="stats-value stats-value-sm">${frappe.utils.escape_html(last_used)}</div>
					</div>
				</div>
				<div class="row" style="margin-top:14px;">
					<div class="col-sm-7">
						<div class="text-muted small mb-1">${__("Tool usage (Top 20)")}</div>
						<div class="table-responsive">
							<table class="table table-sm table-bordered" style="font-size:12px;">
								<thead>
									<tr>
										<th>${__("Tool")}</th>
										<th class="text-right">${__("Calls")}</th>
										<th class="text-right">${__("Success")}</th>
										<th class="text-right">${__("Fail")}</th>
										<th class="text-right">${__("Avg")}</th>
									</tr>
								</thead>
								<tbody>${tool_rows || `<tr><td colspan="5" class="text-muted">${__("No tool calls yet.")}</td></tr>`}</tbody>
							</table>
						</div>
					</div>
					<div class="col-sm-5">
						<div class="text-muted small mb-1">${__("Top users")}</div>
						<div class="table-responsive">
							<table class="table table-sm table-bordered" style="font-size:12px;">
								<thead>
									<tr>
										<th>${__("User")}</th>
										<th class="text-right">${__("Chats")}</th>
										<th class="text-right">${__("Tokens")}</th>
									</tr>
								</thead>
								<tbody>${user_rows || `<tr><td colspan="3" class="text-muted">${__("No usage yet.")}</td></tr>`}</tbody>
							</table>
						</div>
					</div>
				</div>
			`);
		},
		error: () => {
			$host.html(
				`<div class="text-danger small">${__("Could not load stats.")}</div>`
			);
		},
	});
}
