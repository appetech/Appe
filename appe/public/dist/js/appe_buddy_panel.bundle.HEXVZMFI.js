(()=>{frappe.provide("appe.buddy");(function(){"use strict";let u="appe-buddy-floating-drawer",p="appe-buddy-floating-fab",f=null,m=0,_=60*1e3;function h(){!window.frappe||!frappe.session||frappe.session.user==="Guest"||document.getElementById(p)||(y(),c(),o({force:!0}),window.frappe&&frappe.router&&frappe.router.on&&frappe.router.on("change",()=>o({throttle:!0})),$(document).on("appe-buddy-settings-saved",()=>o({force:!0})),window.frappe&&frappe.realtime&&frappe.realtime.on&&frappe.realtime.on("appe_buddy_settings_changed",()=>o({force:!0})),setInterval(()=>o({}),_))}function c(){let n=document.getElementById(p);n&&(n.classList.add("hidden"),n.style.display="none");let e=document.getElementById(u);e&&e.classList.remove("open")}function g(){let n=document.getElementById(p);n&&(n.classList.remove("hidden"),n.style.display="")}function l(n){f=!!n,m=Date.now(),f?g():c()}function o({force:n=!1,throttle:e=!1}={}){let t=Date.now();if(!(e&&!n&&t-m<5e3)){if(!window.frappe||!frappe.call)return c();try{frappe.call({method:"appe.ai.api.settings_public",type:"GET",callback:s=>{let a=s&&s.message&&s.message.data||s&&s.message||{};l(!!a.enabled)},error:()=>l(!1),freeze:!1})}catch(s){l(!1)}}}function y(){let n=document.createElement("button");n.id=p,n.className="appe-buddy-fab hidden",n.style.display="none",n.title=__("Open Appe Buddy"),n.innerHTML='<span class="fa fa-magic"></span>',document.body.appendChild(n);let e=document.createElement("div");e.id=u,e.className="appe-buddy-drawer",e.innerHTML=`
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
						placeholder="${__("Ask about this screen\u2026")}"></textarea>
					<button type="submit" class="btn btn-primary appe-buddy-send-btn">
						<span class="fa fa-paper-plane"></span>
					</button>
				</form>
			</div>
		`,document.body.appendChild(e);let t=new appe.buddy.FloatingPanel(e);n.addEventListener("click",()=>t.toggle()),e.querySelector(".js-close").addEventListener("click",()=>t.close()),e.querySelector(".js-new-chat").addEventListener("click",()=>t.new_chat()),e.querySelector(".js-open-page").addEventListener("click",()=>{t.close(),frappe.set_route("appe-buddy")}),e.querySelector(".appe-buddy-input").addEventListener("submit",a=>{a.preventDefault(),t.send_current()}),e.querySelector(".appe-buddy-textarea").addEventListener("keydown",a=>{a.key==="Enter"&&!a.shiftKey&&(a.preventDefault(),t.send_current())}),window.appe.buddy.floating_panel=t;let s=()=>t.update_context_chip();$(document).on("page-change",s),$(document).on("form-refresh",s),s()}appe.buddy.FloatingPanel=class{constructor(e){this.root=e,this.$drawer=$(e),this.$messages=this.$drawer.find(".appe-buddy-messages"),this.$textarea=this.$drawer.find(".appe-buddy-textarea"),this.$send=this.$drawer.find(".appe-buddy-send-btn"),this.$chip=this.$drawer.find(".context-chip"),this.conversation=null,this.sending=!1,this.opened_once=!1}open(){this.$drawer.addClass("open"),this.opened_once||(this.opened_once=!0,this.bootstrap()),this.update_context_chip(),setTimeout(()=>this.$textarea.trigger("focus"),250)}close(){this.$drawer.removeClass("open")}toggle(){this.$drawer.hasClass("open")?this.close():this.open()}async bootstrap(){try{let e=await this.call("appe.ai.api.list_conversations",{limit:1,status:"Active"});if(Array.isArray(e)&&e.length){this.conversation=e[0].name;let t=await this.call("appe.ai.api.get_conversation",{name:e[0].name,message_limit:50});this.render_messages(t.messages||[]);return}}catch(e){}this.render_empty()}render_empty(){this.$messages.html(`
				<div class="appe-buddy-empty" style="padding:18px 8px;">
					<div class="appe-buddy-empty-icon"><span class="fa fa-magic"></span></div>
					<div class="text-muted small">${__("I see your current screen as context.")}</div>
					<div class="appe-buddy-suggestions" style="margin-top:10px;">
						<button class="btn btn-default btn-xs appe-buddy-suggestion">${__("Summarize this record")}</button>
						<button class="btn btn-default btn-xs appe-buddy-suggestion">${__("Explain what this DocType is for")}</button>
						<button class="btn btn-default btn-xs appe-buddy-suggestion">${__("Suggest 3 improvements")}</button>
					</div>
				</div>
			`),this.$drawer.find(".appe-buddy-suggestion").on("click",e=>{this.$textarea.val($(e.currentTarget).text().trim()).trigger("focus")})}render_messages(e){this.$messages.empty(),(e||[]).forEach(t=>this.append_message_dom(t)),this.scroll_bottom()}append_message_dom(e){let t=e.role;if(t==="system")return;if(t==="tool"){let a=this.summarize_tool_result(e),r=$(`
					<div class="appe-buddy-msg appe-buddy-msg-tool">
						<span class="appe-buddy-tool-chip">
							<span class="fa fa-cogs"></span>
							${frappe.utils.escape_html(e.tool_name||"tool")}
						</span>
						<span class="appe-buddy-tool-summary text-muted small">${a}</span>
					</div>
				`);this.$messages.append(r);return}if(t==="assistant"&&e.tool_name){let a=$(`
					<div class="appe-buddy-msg appe-buddy-msg-assistant">
						<span class="appe-buddy-tool-chip">
							<span class="fa fa-bolt"></span>
							${__("Calling")} <b>${frappe.utils.escape_html(e.tool_name)}</b>
						</span>
					</div>
				`);this.$messages.append(a);return}let s=$(`
				<div class="appe-buddy-msg appe-buddy-msg-${t}">
					<div class="appe-buddy-msg-bubble">${this.format_text(e.content||"")}</div>
				</div>
			`);this.$messages.append(s)}summarize_tool_result(e){let t=e.tool_result;if(!t)return __("done");if(typeof t=="object"){if(t.ok===!1)return`<span class="text-danger">${frappe.utils.escape_html(t.error||"error")}</span>`;let s=t.result||t,r=Object.keys(s||{}).slice(0,3).map(i=>{let d=s[i];return Array.isArray(d)?`${i}: ${d.length}`:typeof d=="object"&&d!==null?`${i}: {\u2026}`:`${i}: ${String(d).slice(0,24)}`});return frappe.utils.escape_html(r.join(" \xB7 ")||"ok")}return frappe.utils.escape_html(String(t).slice(0,140))}format_text(e){return frappe.utils.escape_html(e).replace(/```([\s\S]*?)```/g,(s,a)=>`<pre>${a}</pre>`).replace(/`([^`]+)`/g,"<code>$1</code>").replace(/\n/g,"<br>")}scroll_bottom(){let e=this.$messages[0];e&&(e.scrollTop=e.scrollHeight)}current_context(){let e={source:"floating_panel",route:frappe.get_route&&frappe.get_route().join("/")||window.location.hash};try{let t=frappe.get_route?frappe.get_route():[];if(t[0]==="Form"&&t[1]){if(e.doctype=t[1],t[2]&&(e.docname=t[2]),cur_frm&&cur_frm.doc){let s=cur_frm.doc;e.doctype=s.doctype||e.doctype,e.docname=s.name||e.docname,e.doc_snapshot={},((cur_frm.meta||{}).fields||[]).forEach(r=>{if(["Section Break","Column Break","Tab Break","HTML","Table","Table MultiSelect","Long Text","Text Editor","Markdown Editor","HTML Editor","Code","Signature","Attach","Attach Image","Password"].indexOf(r.fieldtype)===-1){let i=s[r.fieldname];i!=null&&i!==""&&(e.doc_snapshot[r.fieldname]=i)}})}}else t[0]==="List"&&t[1]?(e.doctype=t[1],e.list_view=!0):t[0]==="query-report"&&t[1]?e.report=t[1]:t[0]==="dashboard-view"&&t[1]&&(e.dashboard=t[1])}catch(t){}return e}update_context_chip(){let e=this.current_context(),t=__("Desk");e.doctype&&e.docname?t=`${e.doctype} \xB7 ${e.docname}`:e.doctype?t=e.doctype:e.report?t=`Report \xB7 ${e.report}`:e.dashboard&&(t=`Dashboard \xB7 ${e.dashboard}`),this.$chip.text(t)}async new_chat(){try{let e=await this.call("appe.ai.api.new_conversation",{title:"Quick chat",context:this.current_context()});this.conversation=e.name,this.render_empty()}catch(e){frappe.show_alert({message:e.message||"Failed",indicator:"red"})}}async send_current(){let e=(this.$textarea.val()||"").trim();if(!e||this.sending)return;this.sending=!0,this.$send.prop("disabled",!0).find(".fa").removeClass("fa-paper-plane").addClass("fa-spinner fa-spin"),this.append_message_dom({role:"user",content:e}),this.$textarea.val(""),this.scroll_bottom();let t=$(`
				<div class="appe-buddy-msg appe-buddy-msg-assistant appe-buddy-thinking">
					<div class="appe-buddy-msg-bubble"><span class="fa fa-circle-notch fa-spin"></span> ${__("thinking\u2026")}</div>
				</div>
			`);this.$messages.append(t),this.scroll_bottom();try{let s=await this.call("appe.ai.api.send_message",{message:e,conversation:this.conversation||null,context:this.current_context()});this.conversation=s.conversation,t.remove();let a=await this.call("appe.ai.api.get_conversation",{name:s.conversation,message_limit:100});this.render_messages(a.messages||[])}catch(s){t.remove(),this.append_message_dom({role:"assistant",content:"**Error:** "+(s.message||"Failed")}),this.scroll_bottom()}finally{this.sending=!1,this.$send.prop("disabled",!1).find(".fa").removeClass("fa-spinner fa-spin").addClass("fa-paper-plane")}}call(e,t={}){let s=e.indexOf("send_")!==-1||e.indexOf("new_")!==-1||e.indexOf("rename_")!==-1||e.indexOf("pin_")!==-1||e.indexOf("archive_")!==-1||e.indexOf("delete_")!==-1;return new Promise((a,r)=>{frappe.call({method:e,args:t,type:s?"POST":"GET",callback:i=>{i.message&&i.message.status===!1?r(new Error(i.message.error||"Failed")):i.message&&i.message.data!==void 0?a(i.message.data):i.message?a(i.message):a(null)},error:i=>r(new Error(i.message||"Network error"))})})}},document.readyState==="loading"?document.addEventListener("DOMContentLoaded",()=>$(document).ready(h)):$(document).ready(h)})();})();
//# sourceMappingURL=appe_buddy_panel.bundle.HEXVZMFI.js.map
