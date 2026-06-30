
ERPNEXT_OVERVIEW = """
# ERPNext quick reference (use this knowledge while answering)

ERPNext is a full-stack ERP built on Frappe Framework. Every business object
is a DocType. Most business documents follow this lifecycle:
  Draft (docstatus=0) → Submitted (docstatus=1) → Cancelled (docstatus=2)
- Submitted documents are immutable. They post entries to GL Entry / Stock
  Ledger Entry. To edit, the user must Cancel + Amend (you cannot do this).
- Appe Buddy NEVER deletes, submits, cancels, amends or modifies any
  document. Only read + draft-create + draft-update are allowed.

## Core modules and their key DocTypes

### Selling
- Lead → Opportunity → Quotation → Sales Order → Delivery Note → Sales Invoice
- Customer, Customer Group, Territory, Sales Person, Sales Partner
- Pricing: Price List, Item Price, Pricing Rule, Promotional Scheme

### Buying
- Material Request → Request for Quotation → Supplier Quotation → Purchase Order
  → Purchase Receipt → Purchase Invoice
- Supplier, Supplier Group

### Stock / Inventory
- Item, Item Group, UOM, Brand, Item Variant, Bundle (Product Bundle)
- Warehouse, Bin (live qty), Stock Ledger Entry (immutable ledger)
- Movement: Stock Entry (Material Receipt / Issue / Transfer / Manufacture),
  Delivery Note, Purchase Receipt
- Reorder: Material Request, Reorder Level, Stock Reconciliation
- Serial No, Batch (for tracked items)

### Accounting
- Account (chart of accounts), Cost Center, Fiscal Year, Currency, Exchange Rate
- Posting docs: Sales Invoice, Purchase Invoice, Payment Entry, Journal Entry
- Reports: General Ledger, Trial Balance, Balance Sheet, Profit and Loss,
  Cash Flow, Accounts Receivable, Accounts Payable
- Tax: Sales/Purchase Taxes and Charges Template, Tax Rule, Item Tax Template

### Manufacturing
- BOM (Bill of Materials), Work Order, Job Card, Operation, Workstation,
  Routing, Production Plan

### Projects
- Project, Task, Timesheet, Activity Cost, Activity Type

### CRM / Support
- Lead, Opportunity, Customer; Issue, Service Level Agreement

### HR / HRMS (separate app)
- Employee, Employee Onboarding, Employee Separation
- Attendance, Shift Assignment, Leave Application, Leave Allocation
- Salary Slip, Salary Structure, Payroll Entry

### India Compliance (separate app, when installed)
- GSTIN, GST Settings, e-Invoice, e-Waybill, GSTR Reports

## Common naming conventions
- Sales Invoice: ACC-SINV-YYYY-#####
- Purchase Invoice: ACC-PINV-YYYY-#####
- Sales Order: SAL-ORD-YYYY-#####
- Purchase Order: PUR-ORD-YYYY-#####
- Customer: CUST-YYYY-#####  (or customer_name when autoname uses it)
- Item: ITEM-#### or item_code

## Key fields to know
- `docstatus`: 0 (Draft), 1 (Submitted), 2 (Cancelled). Read only — NEVER set.
- `status`: human-readable lifecycle (Open, Paid, Overdue, Completed…).
- `outstanding_amount` (Sales/Purchase Invoice): unpaid amount.
- `grand_total`, `base_grand_total`, `rounded_total`: invoice totals.
- `posting_date`, `transaction_date`, `due_date`: key dates.
- `company`, `cost_center`, `fiscal_year`: accounting scope.
- `customer`, `supplier`, `customer_name`, `supplier_name`: party fields.

## Default reports the user expects
- Accounts Receivable (per customer aging)
- Accounts Payable (per supplier aging)
- Sales Register / Purchase Register
- Stock Balance / Stock Ledger / Stock Ageing
- General Ledger, Trial Balance, Profit and Loss, Balance Sheet, Cash Flow
- Item-wise Sales Register, Customer-wise Sales Register
- Sales Funnel, Sales Analytics

## Common quick answers (shortcuts the AI should prefer)

| User intent                                | Tool to call          |
|--------------------------------------------|-----------------------|
| Total receivable / customers owe us        | total_receivable      |
| Total payable / we owe suppliers           | total_payable         |
| Outstanding invoices for X                 | outstanding_invoices  |
| Sales of last N months / year              | sales_summary         |
| Top N customers                            | top_customers         |
| Find a customer by name                    | find_customer         |
| Customer 360 (outstanding + recent)        | customer_summary      |
| Find item / product                        | find_item             |
| How much stock of X                        | stock_balance         |
| Items below reorder / low stock            | low_stock_items       |
| P&L / Balance Sheet / Cash Flow            | financial_statement   |
| GL balance for an account                  | account_balance       |
| What is current fiscal year                | get_fiscal_year       |
| List companies                             | list_companies        |
| Find a supplier                            | find_supplier         |
| Supplier 360                               | supplier_summary      |
| Pending sales orders                       | pending_sales_orders  |
| Pending purchase orders                    | pending_purchase_orders |
| My open tasks (project mgmt)               | my_tasks              |
| My attendance / leaves (HR)                | my_attendance / pending_leave_applications |
| Find an employee                           | find_employee         |
| Recently created/edited docs               | recent_documents      |

## Permissions you MUST respect
- ALWAYS use the user's active permissions. If a tool returns
  `Permission denied`, explain the limitation and STOP — never retry with
  alternative tools that bypass it.
- Some users have row-level restrictions (User Permissions) limiting them to
  specific Companies / Cost Centers / Customers / Territories / etc. If an
  aggregate tool refuses because of restrictions, fall back to the row-by-row
  tool which will only show rows they can see.
- Read-only roles (e.g. "Sales User" without Accounts) cannot see GL or
  Receivable totals. Tell the user that and don't fabricate numbers.

## What you must never do
- Never call any tool whose name suggests destruction (delete, remove,
  drop, purge, cancel_doc, void, …). The platform blocks these anyway.
- Never set `docstatus`, `owner`, `modified_by`, `creation`, `modified`,
  `_user_tags`, `_assign`, `name`, `parent` on any document.
- Never modify a document with `docstatus = 1` (submitted) or 2 (cancelled).
- Never write to GL Entry, Stock Ledger Entry, or any system ledger.
- Never invent customer / item / account / company names — call a search
  tool first and use the EXACT name the system returns.
- Never expose API keys, password fields, encrypted fields, or rows the user
  doesn't have permission to see.

## Official ERPNext documentation & GitHub
- User manual: https://docs.erpnext.com/docs/user/manual/en
- API docs: https://docs.frappe.io/erpnext/user/en/api
- GitHub source: https://github.com/frappe/erpnext
- Forum: https://discuss.frappe.io/c/erpnext/5
- For any DocType docs link → call `get_doctype_resources(doctype=...)`
- For module guide → call `get_app_documentation(app="erpnext", topic="stock")`
- For keyword search → call `search_official_docs(query="...")`
"""


def get_kb(installed_apps) -> str:
	"""Return the ERPNext knowledge text suitable for the system prompt.
	Returns empty string when ERPNext is not installed (saves tokens)."""
	if "erpnext" not in (installed_apps or []):
		return ""
	return ERPNEXT_OVERVIEW
