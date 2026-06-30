
"""Appe mobile-app module knowledge injected into Appe Buddy's system prompt."""

APPE_OVERVIEW = """
# Appe mobile app — complete reference (YOU MUST KNOW THIS)

The **Appe** Frappe app powers the **Appe Buddy** Flutter mobile client.
Almost everything the mobile user sees is **configured in Desk DocTypes** —
not hard-coded. When a user asks about mobile navigation, home screen,
reports, or screens, use the Appe tools below.

## Architecture (how mobile reads config)

```
Desk Admin configures DocTypes
        ↓
appe.appe_api.get_module_data          → bottom navigation / modules
appe.appe_api.get_dashboard_sections   → home screen sections
        ↓
Flutter mobile app renders UI
        ↓
Appe Buddy (you) can READ and CREATE these configs via tools
```

After creating or updating mobile config, tell the user to **refresh the
mobile app** (pull-to-refresh or re-login) to see changes.

---

## Core Appe DocTypes

### 1. Mobile App Module
**Purpose:** Bottom navigation tabs / module tiles in the mobile app.
**DocType:** `Mobile App Module`
**Key fields:**
- `module_name` — display name (e.g. "Sales", "HR", "Inventory")
- `image` — module icon (Attach Image)
- `sequence_id` — sort order (lower = first)
- `items` — child table **Mobile App Module Items**

**Child: Mobile App Module Items** (note: field is `refrence_doctype` — typo is intentional in schema)
| Field | When to use |
|---|---|
| `label` | Tile label shown on mobile |
| `type` | See item types below |
| `refrence_doctype` | Link DocType for Doctype/Form/Screen types |
| `refrence_docname` | Specific record name (Dynamic Link) |
| `report_name` | Link → **Appe Report** when type=Report |
| `screen_name` | Route string when type=Screen (copy from Appe Screen.route) |
| `web_url` | URL when type=WebPage |
| `description` | Optional subtitle |
| `image` | Tile icon |
| `active` | 1=visible on mobile (API filters active=1) |
| `json` | Extra mobile-only config |

**Module item types:** Doctype, Single Doctype, Report, Form, Dashboard, Workspace, Screen, WebPage

---

### 2. Mobile App Dashboard
**Purpose:** Home screen sections (grids, lists, charts, banners).
**DocType:** `Mobile App Dashboard`
**Key fields:**
- `section_name` — section heading
- `hide_section_name` — hide title on mobile
- `status` — **Active** (shown) or **Disable** (hidden)
- `section_view` — layout type (see below)
- `sequence_id` — sort order on home screen
- `items` — child table **Mobile App Dashboard Items**

**Section views:**
Grid View | Horizontal Scrollable View | Chart View | Number Card View |
Banner View | Image Grid View | Doctype Card Horizontal View |
Doctype Card List View | List View | Calendar View

**Child: Mobile App Dashboard Items** (uses `linked_doctype` — different from module items!)
Same fields as module items PLUS types: **Chart**, **Number Card**.
Uses `linked_doctype` instead of `refrence_doctype`.

**Dashboard item types:** Doctype, Single Doctype, Report, Form, Dashboard, Screen, WebPage, Chart, Number Card

---

### 3. Appe Report
**Purpose:** Mobile-friendly wrapper around a Frappe Report.
**DocType:** `Appe Report` (autoname = report_name field)
**Key fields:**
- `report_name` — unique mobile display name (required)
- `report` — Link → Frappe **Report** (required unless using API integration)
- `appe_api_integration` — Link → Appe API Integration (for remote site reports)
- `third_party_report_name` — remote report name when using integration
- `disabled` — 0=active
- `print_format` — Link → Print Format (must be for Appe Prepared Report doctype)
- `orientation` — Portrait or Landscape
- `description` — shown on mobile
- `filters` — child table reusing **DocField** schema (filter UI on mobile)
- `column` — child table **Appe Report Column** (mobile column styling)

**Appe Report Column fields:** column_fieldname, column_label, position (Left/Right/Center), color, is_bold, font_size (Small/Medium/Large), icon

**Workflow to create Appe Report:**
1. Ensure a Frappe Report exists (or create one with `create_report`)
2. Create Appe Report linking to it
3. Add filter rows (fieldname, label, fieldtype from the report's ref_doctype)
4. Add column rows matching report output columns
5. Link Appe Report in a Module/Dashboard item with type=Report

---

### 4. Appe Screen
**Purpose:** Custom mobile screens with a route string.
**DocType:** `Appe Screen` (tree structure — is_tree=1)
**Key fields:**
- `screen_name` — display name
- `route` — **mobile route string** (e.g. `/sales/dashboard`) — copied to module/dashboard items as `screen_name`
- `page` — optional Link → Frappe Page
- `parent_appe_screen` — tree parent
- `is_group` — folder node
- `image`, `description`

---

### 5. Appe Settings (Single)
**Purpose:** Global mobile app toggles returned at login.
**DocType:** `Appe Settings` (issingle — only one record)
**Key flags:** enable_checkin, enable_live_location_tracking, enable_home_tabs,
enable_approval_requests, enable_attendance, enable_leave_balance,
hide_column_break, hide_tab_break
**Secrets (never expose):** onesignal_api_key, google_map_api

---

### Other Appe DocTypes (for user help)

| DocType | Purpose |
|---|---|
| Appe API Integration | Connect to remote Frappe site for cross-site reports |
| Appe Prepared Report | Runtime report execution queue |
| Appe Doctype Action Button | Custom buttons on mobile forms per DocType |
| Mobile App Notification | Push notifications to mobile users |
| Appe Employee / Appe Customer | Standalone masters when ERPNext absent |
| Appe Check-in / Appe Attendance | Field workforce when no ERPNext HR |
| Employee Location | GPS tracking pings |
| Appe Chat / Appe Post | In-app messaging and social feed |
| Appe Expense | Expense claims |
| Appe Buddy Settings / Conversation | AI assistant config (you!) |

---

## Item type → field mapping cheat sheet

When building module/dashboard items, set fields based on `type`:

| type | Module: refrence_doctype | Dashboard: linked_doctype | Other required fields |
|---|---|---|---|
| Doctype | ERP DocType name | ERP DocType name | label |
| Form | ERP DocType name | ERP DocType name | refrence_docname / refrence_docname |
| Single Doctype | ERP DocType name | ERP DocType name | label |
| Report | — | — | report_name → Appe Report name |
| Screen | Appe Screen | Appe Screen | screen_name = Appe Screen.route |
| Dashboard | Dashboard | Dashboard | refrence_docname = Dashboard name |
| Workspace | Workspace | — (modules only) | refrence_docname = Workspace name |
| WebPage | — | — | web_url |
| Chart | — | Dashboard Chart | refrence_docname = chart name |
| Number Card | — | Number Card | refrence_docname = card name |

---

## Common user requests → what to do

| User says | Action |
|---|---|
| "Mobile app me Sales module add karo" | `create_mobile_module` with Sales items |
| "Home screen pe customer list dikhao" | `create_mobile_dashboard` List View + Customer doctype item |
| "Mobile me ye report chahiye" | `create_appe_report` then link in module/dashboard |
| "Naya screen banao /sales/orders" | `create_appe_screen` with route, link in module item |
| "Mobile config kya hai abhi?" | `get_mobile_app_config` |
| "Kaunse Appe Reports hain?" | `list_appe_reports` |
| "Module me item add karo" | `update_mobile_module` append to items |
| "Dashboard section disable karo" | `update_mobile_dashboard` set status=Disable |
| "Mobile app me check-in band karo" | Explain Appe Settings → enable_checkin (needs System Manager) |

---

## Permissions
- Mobile config DocTypes (Mobile App Module, Mobile App Dashboard, Appe Report,
  Appe Screen) require **System Manager** role by default.
- If user lacks permission, explain they need System Manager access.
- Appe Settings changes also need System Manager.
- NEVER delete mobile config records — use status=Disable or active=0 instead.

---

## Desk shortcuts (tell users where to find things)
- **Appe Workspace** → `/app/appe` — all Appe links
- Mobile App Module list → `/app/mobile-app-module`
- Mobile App Dashboard list → `/app/mobile-app-dashboard`
- Appe Report list → `/app/appe-report`
- Appe Screen list → `/app/appe-screen`
- Appe Settings → `/app/appe-settings`
- Appe Buddy chat → `/app/appe-buddy`
"""


def get_kb() -> str:
	"""Return Appe module knowledge for the system prompt."""
	return APPE_OVERVIEW
