"""Frappe ecosystem knowledge — official docs, GitHub repos, installed apps."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Official app registry (docs + GitHub + what each app does)
# ---------------------------------------------------------------------------

FRAPPE_APPS: dict[str, dict] = {
	"frappe": {
		"title": "Frappe Framework",
		"github": "https://github.com/frappe/frappe",
		"docs": "https://docs.frappe.io/framework",
		"docs_user_manual": "https://docs.frappe.io/framework/user/en",
		"docs_api": "https://docs.frappe.io/framework/user/en/api",
		"docs_desk": "https://docs.frappe.io/framework/user/en/desk",
		"docs_doctype": "https://docs.frappe.io/framework/user/en/basics-doctypes",
		"forum": "https://discuss.frappe.io",
		"summary": (
			"Core Python/JS web framework. DocTypes, permissions, REST API, Desk UI, "
			"hooks, reports, workspaces, background jobs, caching."
		),
		"key_topics": [
			("DocTypes", "https://docs.frappe.io/framework/user/en/basics-doctypes"),
			("Permissions", "https://docs.frappe.io/framework/user/en/basics-users-and-permissions"),
			("REST API", "https://docs.frappe.io/framework/user/en/api/rest"),
			("Hooks", "https://docs.frappe.io/framework/user/en/python-hooks"),
			("Reports", "https://docs.frappe.io/framework/user/en/desk/reports"),
			("Script Report", "https://docs.frappe.io/framework/user/en/desk/script-report"),
		],
	},
	"erpnext": {
		"title": "ERPNext",
		"github": "https://github.com/frappe/erpnext",
		"docs": "https://docs.erpnext.com",
		"docs_user_manual": "https://docs.erpnext.com/docs/user/manual/en",
		"docs_api": "https://docs.frappe.io/erpnext/user/en/api",
		"forum": "https://discuss.frappe.io/c/erpnext/5",
		"summary": (
			"Open-source ERP: Accounting, CRM, Selling, Buying, Stock, Manufacturing, "
			"Projects, Assets, Support, Quality, Subcontracting."
		),
		"modules": {
			"accounts": "https://docs.erpnext.com/docs/user/manual/en/accounts",
			"selling": "https://docs.erpnext.com/docs/user/manual/en/selling",
			"buying": "https://docs.erpnext.com/docs/user/manual/en/buying",
			"stock": "https://docs.erpnext.com/docs/user/manual/en/stock",
			"manufacturing": "https://docs.erpnext.com/docs/user/manual/en/manufacturing",
			"projects": "https://docs.erpnext.com/docs/user/manual/en/projects",
			"crm": "https://docs.erpnext.com/docs/user/manual/en/CRM",
			"assets": "https://docs.erpnext.com/docs/user/manual/en/asset",
			"support": "https://docs.erpnext.com/docs/user/manual/en/support",
			"setup": "https://docs.erpnext.com/docs/user/manual/en/setting-up",
		},
		"key_topics": [
			("Chart of Accounts", "https://docs.erpnext.com/docs/user/manual/en/chart-of-accounts"),
			("Sales Invoice", "https://docs.erpnext.com/docs/user/manual/en/sales-invoice"),
			("Purchase Invoice", "https://docs.erpnext.com/docs/user/manual/en/purchase-invoice"),
			("Payment Entry", "https://docs.erpnext.com/docs/user/manual/en/payment-entry"),
			("Stock Entry", "https://docs.erpnext.com/docs/user/manual/en/stock-entry"),
			("BOM", "https://docs.erpnext.com/docs/user/manual/en/bill-of-materials"),
			("Fiscal Year", "https://docs.erpnext.com/docs/user/manual/en/fiscal-year"),
			("GST (India)", "https://docs.erpnext.com/docs/user/manual/en/gst-setup"),
		],
	},
	"hrms": {
		"title": "Frappe HR (HRMS)",
		"github": "https://github.com/frappe/hrms",
		"docs": "https://docs.frappe.io/hr",
		"docs_user_manual": "https://docs.frappe.io/hr/en",
		"forum": "https://discuss.frappe.io/c/hr/29",
		"summary": "HR & Payroll: Employee, Attendance, Leave, Shift, Expense Claim, Payroll, Recruitment.",
		"key_topics": [
			("Employee", "https://docs.frappe.io/hr/en/human-resources/employee"),
			("Attendance", "https://docs.frappe.io/hr/en/human-resources/attendance"),
			("Leave Application", "https://docs.frappe.io/hr/en/human-resources/leave-application"),
			("Payroll", "https://docs.frappe.io/hr/en/payroll"),
			("Salary Slip", "https://docs.frappe.io/hr/en/payroll/salary-slip"),
		],
	},
	"india_compliance": {
		"title": "India Compliance",
		"github": "https://github.com/resilient-tech/india-compliance",
		"docs": "https://docs.indiacompliance.app",
		"docs_user_manual": "https://docs.indiacompliance.app/docs",
		"summary": "GST, e-Invoice, e-Waybill, GSTR-1/3B, TDS/TCS for Indian businesses on ERPNext.",
		"key_topics": [
			("GST Settings", "https://docs.indiacompliance.app/docs/category/gst-settings"),
			("e-Invoice", "https://docs.indiacompliance.app/docs/category/e-invoice"),
			("e-Waybill", "https://docs.indiacompliance.app/docs/category/e-waybill"),
			("GSTR-1", "https://docs.indiacompliance.app/docs/category/gstr-1"),
		],
	},
	"education": {
		"title": "Frappe Education",
		"github": "https://github.com/frappe/education",
		"docs": "https://docs.frappe.io/education",
		"summary": "School/college management: Student, Program, Course, Fees, Attendance, Assessment.",
		"key_topics": [
			("Student", "https://docs.frappe.io/education/student"),
			("Program Enrollment", "https://docs.frappe.io/education/program-enrollment"),
			("Fees", "https://docs.frappe.io/education/fees"),
		],
	},
	"appe": {
		"title": "Appe (this app)",
		"github": None,
		"docs": None,
		"summary": "Mobile app shell + Appe Buddy AI. Configured via Mobile App Module, Dashboard, Appe Report, Appe Screen.",
	},
	"lms": {
		"title": "Frappe LMS",
		"github": "https://github.com/frappe/lms",
		"docs": "https://docs.frappe.io/lms",
		"summary": "Learning management: Courses, Batches, Quizzes, Certificates.",
	},
	"helpdesk": {
		"title": "Frappe Helpdesk",
		"github": "https://github.com/frappe/helpdesk",
		"docs": "https://docs.frappe.io/helpdesk",
		"summary": "Customer support ticketing integrated with ERPNext CRM.",
	},
	"wiki": {
		"title": "Frappe Wiki",
		"github": "https://github.com/frappe/wiki",
		"docs": "https://github.com/frappe/wiki",
		"summary": "Internal wiki/knowledge base for teams.",
	},
	"payments": {
		"title": "Payments",
		"github": "https://github.com/frappe/payments",
		"docs": "https://github.com/frappe/payments",
		"summary": "Payment gateway integrations (Razorpay, Stripe, etc.) for ERPNext.",
	},
	"webshop": {
		"title": "Webshop",
		"github": "https://github.com/frappe/webshop",
		"docs": "https://github.com/frappe/webshop",
		"summary": "E-commerce storefront on ERPNext Items.",
	},
	"healthcare": {
		"title": "Marley Health (Healthcare)",
		"github": "https://github.com/frappe/healthcare",
		"docs": "https://docs.frappe.io/healthcare",
		"summary": "Hospital/clinic: Patient, Appointment, Lab, Inpatient.",
	},
	"non_profit": {
		"title": "Non Profit",
		"github": "https://github.com/frappe/non_profit",
		"docs": "https://github.com/frappe/non_profit",
		"summary": "Donor, Member, Grant management for NGOs.",
	},
}

# ERPNext module → docs path slug (for doctype source lookup)
ERPNEXT_MODULE_DOCS: dict[str, str] = {
	"Accounts": "accounts",
	"Selling": "selling",
	"Buying": "buying",
	"Stock": "stock",
	"Manufacturing": "manufacturing",
	"Projects": "projects",
	"CRM": "CRM",
	"Assets": "asset",
	"Support": "support",
	"Setup": "setting-up",
	"HR": "human-resources",
	"Payroll": "payroll",
	"Quality Management": "quality-management",
	"Subcontracting": "subcontracting",
}


def _doctype_to_slug(name: str) -> str:
	"""Convert 'Sales Invoice' → 'sales-invoice' for docs URLs."""
	return name.lower().replace(" ", "-")


def github_source_path(app: str, doctype: str, module: str | None = None) -> str | None:
	"""Best-effort GitHub path to a DocType JSON in source."""
	if app not in ("frappe", "erpnext", "hrms", "india_compliance", "education", "appe"):
		return None
	slug = doctype.lower().replace(" ", "_")
	mod = (module or "").lower().replace(" ", "_")
	if not mod:
		try:
			import frappe
			mod = (frappe.db.get_value("DocType", doctype, "module") or "").lower().replace(" ", "_")
		except Exception:
			mod = "core"
	if app == "frappe":
		return f"https://github.com/frappe/frappe/tree/develop/frappe/{mod}/doctype/{slug}"
	if app == "erpnext":
		return f"https://github.com/frappe/erpnext/tree/develop/erpnext/{mod}/doctype/{slug}"
	if app == "hrms":
		return f"https://github.com/frappe/hrms/tree/develop/hrms/{mod}/doctype/{slug}"
	if app == "india_compliance":
		return f"https://github.com/resilient-tech/india-compliance/tree/develop/india_compliance/{mod}/doctype/{slug}"
	if app == "education":
		return f"https://github.com/frappe/education/tree/develop/education/{mod}/doctype/{slug}"
	if app == "appe":
		return f"https://github.com/frappe/frappe/tree/develop/frappe/{mod}/doctype/{slug}"  # appe may be private
	return None


def erpnext_doctype_doc_url(doctype: str) -> str:
	"""Official ERPNext user-manual URL for a DocType (best-effort)."""
	slug = _doctype_to_slug(doctype)
	return f"https://docs.erpnext.com/docs/user/manual/en/{slug}"


def frappe_doctype_doc_url(doctype: str) -> str:
	slug = _doctype_to_slug(doctype)
	return f"https://docs.frappe.io/framework/user/en/{slug}"


def get_installed_apps_block(installed: list[str]) -> str:
	lines = ["\n# Installed Frappe apps on THIS site\n"]
	for app in installed:
		info = FRAPPE_APPS.get(app, {})
		title = info.get("title") or app
		lines.append(f"- **{title}** (`{app}`)")
		if info.get("summary"):
			lines.append(f"  - {info['summary']}")
		if info.get("docs"):
			lines.append(f"  - Docs: {info['docs']}")
		if info.get("github"):
			lines.append(f"  - GitHub: {info['github']}")
	lines.append(
		"\nWhen user asks 'how does X work in ERPNext' or 'documentation for Y':\n"
		"- Call `get_doctype_resources` for a specific DocType (returns docs + GitHub + local meta).\n"
		"- Call `get_app_documentation` for an entire app.\n"
		"- Call `search_official_docs` for topic/keyword search across official links.\n"
		"- Always share the official doc URL so user can read the full guide.\n"
		"- You do NOT have the full docs corpus in memory — use tools + links, never invent doc content.\n"
	)
	return "\n".join(lines)


ECOSYSTEM_OVERVIEW = """
# Frappe ecosystem — documentation & GitHub reference

## Official documentation hubs
| Resource | URL |
|---|---|
| Frappe Framework docs | https://docs.frappe.io/framework |
| ERPNext user manual | https://docs.erpnext.com/docs/user/manual/en |
| ERPNext API | https://docs.frappe.io/erpnext/user/en/api |
| Frappe HR (HRMS) | https://docs.frappe.io/hr |
| India Compliance | https://docs.indiacompliance.app |
| Frappe Education | https://docs.frappe.io/education |
| Frappe LMS | https://docs.frappe.io/lms |
| Frappe Cloud | https://frappecloud.com/docs |
| Discuss Forum | https://discuss.frappe.io |
| Bench CLI | https://docs.frappe.io/framework/user/en/bench |

## Official GitHub organizations & repos
| App | GitHub |
|---|---|
| Frappe Framework | https://github.com/frappe/frappe |
| ERPNext | https://github.com/frappe/erpnext |
| HRMS | https://github.com/frappe/hrms |
| India Compliance | https://github.com/resilient-tech/india-compliance |
| Education | https://github.com/frappe/education |
| LMS | https://github.com/frappe/lms |
| Helpdesk | https://github.com/frappe/helpdesk |
| Payments | https://github.com/frappe/payments |
| Webshop | https://github.com/frappe/webshop |
| Healthcare | https://github.com/frappe/healthcare |
| Wiki | https://github.com/frappe/wiki |
| Bench | https://github.com/frappe/bench |

## How to help users with documentation questions
1. **Specific DocType** (e.g. "Sales Invoice kaise banate hain?")
   → `get_doctype_resources(doctype="Sales Invoice")` — returns official doc link,
     GitHub source, local fields, and desk link.
2. **Whole module** (e.g. "Stock module explain karo")
   → `get_app_documentation(app="erpnext", topic="stock")`
3. **Keyword search** (e.g. "GST e-invoice setup")
   → `search_official_docs(query="e-invoice")`
4. **List what's installed**
   → `list_frappe_ecosystem_apps()`
5. Always give the user the **clickable official doc URL**. Say clearly if you are
   summarising from local data vs pointing to official docs.

## ERPNext version note
This site runs the installed version locally. Official docs may reflect latest release;
if behaviour differs, check the GitHub source for the installed version branch.
"""


def get_kb(installed_apps: list[str] | None = None) -> str:
	parts = [ECOSYSTEM_OVERVIEW]
	if installed_apps:
		parts.append(get_installed_apps_block(installed_apps))
	return "\n".join(parts)
