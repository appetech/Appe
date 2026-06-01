# Appe Buddy

Appe Buddy is the AI assistant baked into the **appe** Frappe app. It is designed
to be consumed by the Flutter mobile app of the same name and is capable of
reading data, writing documents, and building new artifacts — DocTypes, Reports,
Dashboard Charts, Number Cards, and Dashboards — all on behalf of the logged-in
user, respecting Frappe permissions.

## What was added

```
appe/
├─ ai/
│  ├─ __init__.py
│  ├─ providers.py        ← OpenAI / OpenAI-compatible / Anthropic / Gemini clients
│  ├─ tools.py            ← Base tool catalog (create_doctype, create_report, ...)
│  ├─ erpnext_tools.py    ← ERPNext-specific tools (auto-loaded if ERPNext is installed)
│  ├─ buddy.py            ← Tool-calling orchestrator (with data-aware system prompt)
│  ├─ api.py              ← Whitelisted REST API for the Flutter app
│  └─ README.md
├─ appe/doctype/
│  ├─ appe_buddy_settings/        (Single — provider/model/capabilities)
│  ├─ appe_buddy_conversation/    (per-user chat sessions)
│  ├─ appe_buddy_message/         (child table inside Conversation)
│  └─ appe_buddy_tool_log/        (audit log of every tool call)
├─ appe/page/appe_buddy/          ← Full-page Desk chat at /app/appe-buddy
└─ public/{js,css}/appe_buddy_panel.{js,css}  ← Floating side panel on every Desk page
```

## Two ways to chat from Desk

### 1. Full page – `/app/appe-buddy`
Two-pane layout (conversation list ←→ chat). Open it from:
- Workspace `Appe → Open Appe Buddy` (shortcut card)
- Direct URL `/app/appe-buddy`

### 2. Floating side panel
A floating button appears at the bottom-right on every Desk page. Click it to
open a slide-in panel. The panel automatically attaches the current page as
context — current route, DocType, document name, and a snapshot of the
currently loaded record's scalar fields — so the AI grounds its answers in
exactly what you're looking at.

> Example: opening a `Sales Invoice` form and asking "summarize this and
> show outstanding for this customer" gives the AI both the invoice fields
> and a hint to call `customer_summary` for the linked customer.

## One-time setup

1. `bench --site <site> migrate` (already done).
2. Open **Desk → Appe → Appe Buddy → Appe Buddy Settings** and fill:
   - **Provider**: `OpenAI`, `OpenAI Compatible`, `Anthropic`, or `Gemini`.
   - **Model**: e.g. `gpt-4o-mini`, `gpt-4o`, `claude-3-5-sonnet-20241022`, `gemini-1.5-flash`.
   - **API Key**: your provider key (stored encrypted via Frappe Password).
   - **API Base URL** (optional): for Azure, Ollama, OpenRouter, LM Studio etc.
3. Tick the **Capabilities** you want the AI to have (create DocType / Report
   / Chart / Dashboard / Number Card / Query Data / Run Report). They are all
   on by default.
4. Click **Test Connection** to make sure your credentials work.
5. Add roles to **Allowed Roles** (default: `System Manager`). Add `Employee` if
   you want all employees to chat with Appe Buddy from the mobile app.

## Capabilities

The assistant has the following tools (filtered by capability flags at runtime):

| Tool | Purpose |
| --- | --- |
| `get_current_user` | Identify the logged-in user and their roles |
| `list_doctypes` | Discover available DocTypes |
| `get_doctype_meta` | Read fields/metadata of a DocType |
| `query_data` | Read records (respects user permissions, max-rows capped) |
| `count_records` | Count records with filters |
| `create_document` | Create any record the user can create |
| `update_document` | Update any record the user can write |
| `create_doctype` | Spin up a brand new custom DocType |
| `list_reports` / `run_report` | Discover and execute existing reports |
| `create_report` | Build new Report Builder / Query Reports |
| `create_dashboard_chart` | Build line/bar/donut/pie/percent/heatmap charts |
| `create_number_card` | Build KPI tiles |
| `create_dashboard` | Compose charts + cards into a Dashboard |

### ERPNext tools (auto-registered when ERPNext is installed)

| Tool | Purpose |
| --- | --- |
| `list_companies` | List companies, returns user's default company |
| `find_customer` | Search Customer master by keyword |
| `customer_summary` | Outstanding amount + recent invoices + open orders for a customer |
| `outstanding_invoices` | Open Sales/Purchase invoices, optional filters |
| `sales_summary` | Monthly sales totals (for charts/answers) |
| `top_customers` | Top N customers by sales total in a date range |
| `find_item` | Search Item master by code/name/description |
| `stock_balance` | Per-warehouse stock for an item (or all items in a warehouse) |
| `financial_statement` | Run P&L / Balance Sheet / Cash Flow / Trial Balance |
| `account_balance` | Live GL balance for a chart-of-accounts account |

### Data-aware system prompt

`buddy._enriched_system_prompt` automatically prepends the configured system
prompt with environment facts so the model never guesses:

- Site name, installed apps (ERPNext / HRMS / India Compliance detection)
- Current user, full name, roles
- Default Company and default Currency
- Strict instructions to always use tools, never invent record names, and
  respect user permissions

Hard-blocked DocTypes (always denied, even if a user has access):
`User`, `Role`, `DocPerm`, `Custom DocPerm`, `Server Script`, `Client Script`,
`OAuth Bearer Token`, `OAuth Authorization Code`, `OAuth Provider Settings`,
`Appe Buddy Settings`, `Appe Buddy Tool Log`, `System Settings`, `Website Settings`.
You can extend this with **Blocked DocTypes** in settings.

Every tool call is recorded in **Appe Buddy Tool Log** with arguments, result,
status, and duration — handy for audits and debugging.

## REST API (for the Flutter "Appe Buddy" mobile app)

All endpoints require authentication (use `Authorization: token <api_key>:<api_secret>`
or a session cookie). Responses follow:

```json
{ "status": true,  "data": ... }
{ "status": false, "error": "..." }
```

### Send a message

`POST /api/method/appe.ai.api.send_message`

```json
{
  "message": "List my open leave applications and chart approvals per month.",
  "conversation": "BUDDY-2026-05-00001",   // optional; if omitted a new convo is created
  "title": "Leave dashboard",              // optional, used only for new conversations
  "context": {                              // optional, JSON. Flutter sends current screen info
    "screen": "leave_list",
    "doctype": "Leave Application",
    "filters": {"status": "Open"}
  }
}
```

Response:

```json
{
  "status": true,
  "data": {
    "conversation": "BUDDY-2026-05-00001",
    "reply": "Created chart 'Leave Approvals 2026' and ran the query. ...",
    "usage": {"total_tokens": 1342},
    "messages": [
      {"role": "user", "content": "...", "created_at": "2026-05-28 19:01:00"},
      {"role": "assistant", "content": "", "tool_name": "query_data",
       "tool_arguments": {"doctype": "Leave Application", "filters": {"status": "Open"}}},
      {"role": "tool", "tool_name": "query_data", "tool_result": {"ok": true, "result": {...}}},
      {"role": "assistant", "content": "Here are your open leaves..."}
    ]
  }
}
```

### Conversations

| Method | Endpoint | Body / Args | Purpose |
| --- | --- | --- | --- |
| POST  | `appe.ai.api.new_conversation`        | `title?`, `context?` | Create a fresh chat |
| GET   | `appe.ai.api.list_conversations`      | `limit?`, `status?` (Active/Archived) | List user's chats |
| GET   | `appe.ai.api.get_conversation`        | `name`, `message_limit?` | Fetch full chat with messages |
| POST  | `appe.ai.api.rename_conversation`     | `name`, `title` | Rename |
| POST  | `appe.ai.api.pin_conversation`        | `name`, `pinned` | Pin / unpin |
| POST  | `appe.ai.api.archive_conversation`    | `name` | Archive |
| POST  | `appe.ai.api.unarchive_conversation`  | `name` | Unarchive |
| POST  | `appe.ai.api.delete_conversation`     | `name` | Permanently delete |

### Misc

| Endpoint | Purpose |
| --- | --- |
| `appe.ai.api.list_tools`      | Returns the tool catalog (capability-aware) |
| `appe.ai.api.settings_public` | Public settings: `enabled`, `provider`, `model`, capability flags |
| `appe.ai.api.test_connection` | Pings the configured provider |

## Flutter integration cheat sheet

```dart
// lib/services/appe_buddy_service.dart
import 'package:dio/dio.dart';

class AppeBuddyService {
  AppeBuddyService(this._dio);
  final Dio _dio;

  Future<Map<String, dynamic>> sendMessage({
    required String message,
    String? conversation,
    String? title,
    Map<String, dynamic>? context,
  }) async {
    final resp = await _dio.post(
      '/api/method/appe.ai.api.send_message',
      data: {
        'message': message,
        if (conversation != null) 'conversation': conversation,
        if (title != null) 'title': title,
        if (context != null) 'context': context,
      },
    );
    final body = resp.data is Map ? resp.data['message'] : resp.data;
    if (body['status'] == true) return body['data'];
    throw Exception(body['error'] ?? 'Appe Buddy failed');
  }

  Future<List<dynamic>> listConversations({String? status, int limit = 50}) async {
    final resp = await _dio.get(
      '/api/method/appe.ai.api.list_conversations',
      queryParameters: {'limit': limit, if (status != null) 'status': status},
    );
    return (resp.data['message']['data'] as List);
  }

  Future<Map<String, dynamic>> getConversation(String name, {int messageLimit = 100}) async {
    final resp = await _dio.get(
      '/api/method/appe.ai.api.get_conversation',
      queryParameters: {'name': name, 'message_limit': messageLimit},
    );
    return resp.data['message']['data'] as Map<String, dynamic>;
  }
}
```

> Note: Frappe wraps whitelisted responses inside a top-level `message` key when
> served over HTTP. The Dart helper above unwraps that for you.

### Auth

The mobile app should reuse the API key/secret minted by your existing
`appe.appe_api.login_user` flow. Set the header:

```
Authorization: token <api_key>:<api_secret>
```

### Suggested chat screen flow

1. On chat screen open → call `list_conversations`, show sidebar.
2. User taps "New chat" → call `new_conversation` (or just send the first
   message without `conversation` and `send_message` will create one).
3. On every send: call `send_message` with the current `conversation` name
   and the user's text. Pass a small `context` object describing the screen
   the user is on — Buddy will use it to ground answers.
4. Show every item in `data.messages` (newest at the bottom). Treat
   `tool_name` rows as "AI did X" indicators (e.g. "Created chart Sales 2026").

## Safety & extensibility

- All write actions go through normal Frappe permissions and the user's session.
- Sensitive DocTypes are hard-blocked, with an additional admin block-list.
- Capability flags let admins disable specific abilities (e.g. no DocType
  creation in production).
- To add a new tool: register it in `appe/ai/tools.py` via
  `register(Tool(name=..., description=..., parameters=..., handler=...))`.
  Tools automatically appear in the assistant's tool list.

## Supported providers

| Provider | Notes |
| --- | --- |
| **OpenAI** | Native tool calling. Default base `https://api.openai.com/v1`. |
| **OpenAI Compatible** | Same wire format. Set `API Base URL` to your endpoint (Azure, OpenRouter, vLLM, Ollama OpenAI shim, LM Studio). |
| **Anthropic** | Claude tool use. Default `https://api.anthropic.com/v1`. |
| **Gemini** | Google Gen AI v1beta. Default `https://generativelanguage.googleapis.com/v1beta`. |
