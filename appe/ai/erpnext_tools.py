from __future__ import annotations

import json
from typing import Any

import frappe

from .tools import (
	Tool,
	_check_user_can,
	_ensure_capability,
	_ensure_doctype_allowed,
	_require_unrestricted,
	_settings,
	register,
)


def is_erpnext_installed() -> bool:
	try:
		return "erpnext" in (frappe.get_installed_apps() or [])
	except Exception:
		return False


def _max_rows() -> int:
	return int(_settings().max_query_rows or 200)


def _default_company() -> str | None:
	try:
		return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
			"Global Defaults", "default_company"
		)
	except Exception:
		return None


def _current_fiscal_year() -> dict | None:
	try:
		today = frappe.utils.today()
		row = frappe.db.sql(
			"""
			SELECT name, year_start_date, year_end_date
			FROM `tabFiscal Year`
			WHERE disabled = 0 AND year_start_date <= %s AND year_end_date >= %s
			ORDER BY year_start_date DESC
			LIMIT 1
			""",
			(today, today),
			as_dict=True,
		)
		if row:
			r = row[0]
			return {
				"name": r["name"],
				"from_date": str(r["year_start_date"]),
				"to_date": str(r["year_end_date"]),
			}
	except Exception:
		pass
	return None


def _resolve_company(company: str | None) -> str | None:
	
	if not company:
		return None
	if frappe.db.exists("Company", company):
		return company
	# Case-insensitive exact
	row = frappe.db.sql(
		"SELECT name FROM `tabCompany` WHERE LOWER(name) = LOWER(%s) LIMIT 1",
		(company,),
		as_dict=True,
	)
	if row:
		return row[0]["name"]
	# Substring (left side) — pick if unique
	candidates = frappe.db.sql(
		"SELECT name FROM `tabCompany` WHERE name LIKE %s",
		(f"%{company}%",),
		as_dict=True,
	)
	if len(candidates) == 1:
		return candidates[0]["name"]
	return None


# ---------------------------------------------------------------------------
# Generic ERPNext discovery
# ---------------------------------------------------------------------------


def _h_list_companies(args: dict, ctx: dict) -> dict:
	_check_user_can("read", "Company")
	rows = frappe.get_all(
		"Company",
		fields=["name", "abbr", "default_currency", "country"],
		limit=int(args.get("limit") or 50),
		order_by="name",
	)
	return {"count": len(rows), "companies": rows, "default": _default_company()}


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------


def _h_find_customer(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "find_customer")
	_check_user_can("read", "Customer")
	kw = (args.get("keyword") or "").strip()
	filters: dict = {"disabled": 0}
	if kw:
		filters["customer_name"] = ["like", f"%{kw}%"]
	rows = frappe.get_list(
		"Customer",
		filters=filters,
		fields=[
			"name",
			"customer_name",
			"customer_group",
			"territory",
			"customer_type",
			"mobile_no",
			"email_id",
		],
		order_by="customer_name",
		limit_page_length=min(int(args.get("limit") or 20), _max_rows()),
	)
	return {"count": len(rows), "customers": rows}


def _h_customer_summary(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "customer_summary")
	customer = args["customer"]
	_check_user_can("read", "Customer")
	_check_user_can("read", "Sales Invoice")
	_check_user_can("read", "Sales Order")
	_require_unrestricted("Sales Invoice", "customer_summary")

	outstanding = (
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(outstanding_amount), 0) AS amt
			FROM `tabSales Invoice`
			WHERE docstatus = 1 AND customer = %s
			""",
			(customer,),
			as_dict=True,
		)
		or [{"amt": 0}]
	)[0]["amt"]

	recent_invoices = frappe.get_all(
		"Sales Invoice",
		filters={"customer": customer},
		fields=[
			"name",
			"posting_date",
			"grand_total",
			"outstanding_amount",
			"status",
			"due_date",
		],
		order_by="posting_date desc",
		limit_page_length=5,
	)
	open_orders = frappe.get_all(
		"Sales Order",
		filters={"customer": customer, "status": ["not in", ["Closed", "Cancelled", "Completed"]]},
		fields=["name", "transaction_date", "grand_total", "status", "delivery_date"],
		order_by="transaction_date desc",
		limit_page_length=10,
	)
	cust = frappe.db.get_value(
		"Customer",
		customer,
		["customer_name", "customer_group", "territory", "mobile_no", "email_id"],
		as_dict=True,
	)
	return {
		"customer": customer,
		"details": cust,
		"outstanding_amount": float(outstanding or 0),
		"recent_invoices": recent_invoices,
		"open_sales_orders": open_orders,
	}


def _h_outstanding_invoices(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "outstanding_invoices")
	_check_user_can("read", "Sales Invoice")
	party_type = args.get("party_type") or "Customer"
	if party_type not in ("Customer", "Supplier"):
		raise ValueError("party_type must be Customer or Supplier")
	doctype = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
	_check_user_can("read", doctype)

	raw_company = args.get("company")
	resolved_company = _resolve_company(raw_company) if raw_company else None
	# Don't add company filter when caller passed a bad name — that turned 296k → 0
	if raw_company and not resolved_company:
		company_used = None
		company_note = (
			f"Requested company '{raw_company}' did not match any Company. "
			f"Returning results across all companies. Call list_companies for exact names."
		)
	else:
		company_used = resolved_company
		company_note = None

	filters: dict[str, Any] = {"outstanding_amount": [">", 0], "docstatus": 1}
	if args.get("party"):
		filters["customer" if party_type == "Customer" else "supplier"] = args["party"]
	if company_used:
		filters["company"] = company_used

	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=[
			"name",
			"customer" if party_type == "Customer" else "supplier",
			"posting_date",
			"due_date",
			"grand_total",
			"outstanding_amount",
			"status",
			"company",
		],
		order_by="due_date asc",
		limit_page_length=min(int(args.get("limit") or 50), _max_rows()),
	)
	total = sum((r.get("outstanding_amount") or 0) for r in rows)

	# Smart retry: caller specified company but got 0 — show what exists elsewhere
	if not rows and company_used:
		other = frappe.db.sql(
			f"""
			SELECT company, COUNT(*) AS cnt, COALESCE(SUM(outstanding_amount), 0) AS total
			FROM `tab{doctype}`
			WHERE outstanding_amount > 0 AND docstatus = 1
			GROUP BY company
			""",
			as_dict=True,
		)
		other_total = sum((r.get("total") or 0) for r in other)
		if other_total:
			company_note = (
				f"No outstanding {doctype} for company '{company_used}'. "
				f"Other companies hold a total of {other_total:.2f}: "
				+ ", ".join(f"{r['company']}={float(r['total'] or 0):.2f}" for r in other)
				+ ". Call this tool again without 'company' to see all."
			)

	out = {
		"party_type": party_type,
		"doctype": doctype,
		"count": len(rows),
		"total_outstanding": float(total),
		"company": company_used,
		"rows": rows,
	}
	if company_note:
		out["note"] = company_note
	return out


def _h_sales_summary(args: dict, ctx: dict) -> dict:
	"""Sales totals for a period grouped by month."""
	_ensure_capability("allow_query_data", "sales_summary")
	_check_user_can("read", "Sales Invoice")
	_require_unrestricted("Sales Invoice", "sales_summary")
	from_date = args.get("from_date")
	to_date = args.get("to_date")
	# If no dates given, default to current fiscal year (NOT calendar year)
	if not from_date and not to_date:
		fy = _current_fiscal_year()
		if fy:
			from_date = fy["from_date"]
			to_date = fy["to_date"]
	company = _resolve_company(args.get("company"))
	where = ["docstatus = 1"]
	params: list[Any] = []
	if from_date:
		where.append("posting_date >= %s")
		params.append(from_date)
	if to_date:
		where.append("posting_date <= %s")
		params.append(to_date)
	if company:
		where.append("company = %s")
		params.append(company)
	sql = f"""
		SELECT
			DATE_FORMAT(posting_date, '%%Y-%%m') AS month,
			COUNT(*) AS invoices,
			SUM(grand_total) AS total,
			SUM(outstanding_amount) AS outstanding
		FROM `tabSales Invoice`
		WHERE {' AND '.join(where)}
		GROUP BY DATE_FORMAT(posting_date, '%%Y-%%m')
		ORDER BY month DESC
		LIMIT 36
	"""
	rows = frappe.db.sql(sql, tuple(params), as_dict=True)
	for r in rows:
		r["total"] = float(r.get("total") or 0)
		r["outstanding"] = float(r.get("outstanding") or 0)
	return {"company": company, "buckets": rows, "currency": _company_currency(company)}


def _h_top_customers(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "top_customers")
	_check_user_can("read", "Sales Invoice")
	_require_unrestricted("Sales Invoice", "top_customers")
	limit = min(int(args.get("limit") or 10), 50)
	company = _resolve_company(args.get("company"))
	from_date = args.get("from_date")
	to_date = args.get("to_date")
	if not from_date and not to_date:
		fy = _current_fiscal_year()
		if fy:
			from_date = fy["from_date"]
			to_date = fy["to_date"]
	where = ["docstatus = 1"]
	params: list[Any] = []
	if company:
		where.append("company = %s")
		params.append(company)
	if from_date:
		where.append("posting_date >= %s")
		params.append(from_date)
	if to_date:
		where.append("posting_date <= %s")
		params.append(to_date)
	sql = f"""
		SELECT customer, SUM(grand_total) AS total, COUNT(*) AS invoices
		FROM `tabSales Invoice`
		WHERE {' AND '.join(where)}
		GROUP BY customer
		ORDER BY total DESC
		LIMIT {limit}
	"""
	rows = frappe.db.sql(sql, tuple(params), as_dict=True)
	for r in rows:
		r["total"] = float(r.get("total") or 0)
	return {"company": company, "rows": rows, "currency": _company_currency(company)}


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def _h_find_item(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "find_item")
	_check_user_can("read", "Item")
	kw = (args.get("keyword") or "").strip()
	filters: dict = {"disabled": 0}
	if kw:
		# match either item_code or item_name
		rows = frappe.db.sql(
			"""
			SELECT name, item_code, item_name, item_group, stock_uom, is_stock_item,
			       standard_rate, has_variants
			FROM `tabItem`
			WHERE disabled = 0
			  AND (item_code LIKE %(kw)s OR item_name LIKE %(kw)s OR description LIKE %(kw)s)
			ORDER BY item_name
			LIMIT %(limit)s
			""",
			{"kw": f"%{kw}%", "limit": int(args.get("limit") or 20)},
			as_dict=True,
		)
	else:
		rows = frappe.get_list(
			"Item",
			filters=filters,
			fields=[
				"name",
				"item_code",
				"item_name",
				"item_group",
				"stock_uom",
				"is_stock_item",
				"standard_rate",
				"has_variants",
			],
			order_by="modified desc",
			limit_page_length=int(args.get("limit") or 20),
		)
	return {"count": len(rows), "items": rows}


def _h_stock_balance(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "stock_balance")
	_check_user_can("read", "Bin")
	item_code = args.get("item_code")
	warehouse = args.get("warehouse")
	if not item_code and not warehouse:
		raise ValueError("Provide at least one of item_code or warehouse")
	filters: dict[str, Any] = {}
	if item_code:
		filters["item_code"] = item_code
	if warehouse:
		filters["warehouse"] = warehouse
	rows = frappe.get_list(
		"Bin",
		filters=filters,
		fields=[
			"name",
			"item_code",
			"warehouse",
			"actual_qty",
			"reserved_qty",
			"projected_qty",
			"valuation_rate",
			"stock_value",
		],
		order_by="warehouse",
		limit_page_length=min(int(args.get("limit") or 50), _max_rows()),
	)
	total_qty = sum((r.get("actual_qty") or 0) for r in rows)
	total_value = sum((r.get("stock_value") or 0) for r in rows)
	return {
		"item_code": item_code,
		"warehouse": warehouse,
		"rows": rows,
		"total_actual_qty": float(total_qty),
		"total_stock_value": float(total_value),
	}


# ---------------------------------------------------------------------------
# Accounting
# ---------------------------------------------------------------------------


def _company_currency(company: str | None) -> str | None:
	if not company:
		return None
	return frappe.db.get_value("Company", company, "default_currency")


def _h_financial_statement(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_run_report", "financial_statement")
	statement = (args.get("statement") or "Profit and Loss Statement").strip()
	allowed = {
		"Profit and Loss Statement",
		"Balance Sheet",
		"Cash Flow",
		"Trial Balance",
	}
	if statement not in allowed:
		raise ValueError(f"statement must be one of {sorted(allowed)}")

	if not frappe.db.exists("Report", statement):
		raise ValueError(f"Report '{statement}' not found")
	_check_user_can("read", frappe.db.get_value("Report", statement, "ref_doctype") or "Account")

	from frappe.desk.query_report import run as run_query_report

	company = args.get("company") or _default_company()
	if not company:
		raise ValueError("company is required")
	from_date = args.get("from_date")
	to_date = args.get("to_date")
	if not from_date or not to_date:
		# Default to current fiscal year if available
		fy = frappe.defaults.get_user_default("fiscal_year") or frappe.db.get_value(
			"Fiscal Year", {"disabled": 0}, "name", order_by="year_start_date desc"
		)
		if fy:
			fy_doc = frappe.db.get_value(
				"Fiscal Year",
				fy,
				["year_start_date", "year_end_date"],
				as_dict=True,
			)
			from_date = from_date or str(fy_doc.year_start_date)
			to_date = to_date or str(fy_doc.year_end_date)
	if not from_date or not to_date:
		raise ValueError("from_date and to_date are required (no fiscal year fallback)")
	filters = {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"periodicity": args.get("periodicity") or "Yearly",
		"filter_based_on": "Date Range",
		"accumulated_values": 1,
	}
	result = run_query_report(report_name=statement, filters=filters, user=frappe.session.user)
	rows = result.get("result") or []
	max_rows = _max_rows()
	return {
		"statement": statement,
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"currency": _company_currency(company),
		"columns": result.get("columns") or [],
		"row_count": len(rows),
		"rows": rows[:max_rows],
		"truncated": len(rows) > max_rows,
	}


def _h_account_balance(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "account_balance")
	_check_user_can("read", "GL Entry")
	_require_unrestricted("GL Entry", "account_balance")
	account = args["account"]
	as_of = args.get("as_of")
	company = _resolve_company(args.get("company"))
	where = ["account = %s", "docstatus < 2"]
	params: list[Any] = [account]
	if company:
		where.append("company = %s")
		params.append(company)
	if as_of:
		where.append("posting_date <= %s")
		params.append(as_of)
	sql = f"""
		SELECT COALESCE(SUM(debit) - SUM(credit), 0) AS balance,
		       COALESCE(SUM(debit), 0) AS total_debit,
		       COALESCE(SUM(credit), 0) AS total_credit
		FROM `tabGL Entry`
		WHERE {' AND '.join(where)}
	"""
	row = frappe.db.sql(sql, tuple(params), as_dict=True)[0]
	return {
		"account": account,
		"company": company,
		"as_of": as_of,
		"balance": float(row.get("balance") or 0),
		"total_debit": float(row.get("total_debit") or 0),
		"total_credit": float(row.get("total_credit") or 0),
		"currency": _company_currency(company),
	}


def _h_total_receivable(args: dict, ctx: dict) -> dict:
	
	_ensure_capability("allow_query_data", "total_receivable")
	_check_user_can("read", "GL Entry")
	_check_user_can("read", "Account")
	# Aggregate over GL — only safe when user has unrestricted access. A user
	# with a Company-scoped User Permission would otherwise see the full
	# group's receivable; refuse rather than leak.
	_require_unrestricted("GL Entry", "total_receivable")
	company = _resolve_company(args.get("company"))
	as_of = args.get("as_of")

	where = ["a.account_type = 'Receivable'", "g.docstatus < 2"]
	params: list[Any] = []
	if company:
		where.append("g.company = %s")
		params.append(company)
	if as_of:
		where.append("g.posting_date <= %s")
		params.append(as_of)

	sql = f"""
		SELECT g.company,
		       COALESCE(SUM(g.debit - g.credit), 0) AS receivable,
		       a.account_currency
		FROM `tabGL Entry` g
		JOIN `tabAccount` a ON g.account = a.name
		WHERE {' AND '.join(where)}
		GROUP BY g.company, a.account_currency
		ORDER BY receivable DESC
	"""
	rows = frappe.db.sql(sql, tuple(params), as_dict=True)
	for r in rows:
		r["receivable"] = float(r.get("receivable") or 0)
	total = sum(r["receivable"] for r in rows)
	return {
		"company": company,
		"as_of": as_of,
		"total_receivable": float(total),
		"by_company": rows,
	}


def _h_total_payable(args: dict, ctx: dict) -> dict:
	"""Total accounts-payable balance from GL Entries."""
	_ensure_capability("allow_query_data", "total_payable")
	_check_user_can("read", "GL Entry")
	_check_user_can("read", "Account")
	_require_unrestricted("GL Entry", "total_payable")
	company = _resolve_company(args.get("company"))
	as_of = args.get("as_of")
	where = ["a.account_type = 'Payable'", "g.docstatus < 2"]
	params: list[Any] = []
	if company:
		where.append("g.company = %s")
		params.append(company)
	if as_of:
		where.append("g.posting_date <= %s")
		params.append(as_of)
	sql = f"""
		SELECT g.company,
		       COALESCE(SUM(g.credit - g.debit), 0) AS payable,
		       a.account_currency
		FROM `tabGL Entry` g
		JOIN `tabAccount` a ON g.account = a.name
		WHERE {' AND '.join(where)}
		GROUP BY g.company, a.account_currency
		ORDER BY payable DESC
	"""
	rows = frappe.db.sql(sql, tuple(params), as_dict=True)
	for r in rows:
		r["payable"] = float(r.get("payable") or 0)
	total = sum(r["payable"] for r in rows)
	return {
		"company": company,
		"as_of": as_of,
		"total_payable": float(total),
		"by_company": rows,
	}


def _h_get_fiscal_year(args: dict, ctx: dict) -> dict:
	
	_check_user_can("read", "Fiscal Year")
	year = args.get("year")
	if year:
		row = frappe.db.get_value(
			"Fiscal Year",
			year,
			["name", "year_start_date", "year_end_date", "disabled"],
			as_dict=True,
		)
		if not row:
			raise ValueError(f"Fiscal Year '{year}' not found")
		return {
			"name": row.name,
			"from_date": str(row.year_start_date),
			"to_date": str(row.year_end_date),
			"is_current": row.year_start_date <= frappe.utils.getdate(frappe.utils.today()) <= row.year_end_date,
		}
	# current
	fy = _current_fiscal_year()
	if not fy:
		raise ValueError("No fiscal year found for today's date")
	fy["is_current"] = True
	return fy


# ---------------------------------------------------------------------------
# Suppliers / Buying
# ---------------------------------------------------------------------------


def _h_find_supplier(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "find_supplier")
	_check_user_can("read", "Supplier")
	kw = (args.get("keyword") or "").strip()
	filters: dict = {"disabled": 0}
	if kw:
		filters["supplier_name"] = ["like", f"%{kw}%"]
	rows = frappe.get_list(
		"Supplier",
		filters=filters,
		fields=[
			"name",
			"supplier_name",
			"supplier_group",
			"supplier_type",
			"country",
			"mobile_no",
			"email_id",
		],
		order_by="supplier_name",
		limit_page_length=min(int(args.get("limit") or 20), _max_rows()),
	)
	return {"count": len(rows), "suppliers": rows}


def _h_supplier_summary(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "supplier_summary")
	supplier = args["supplier"]
	_check_user_can("read", "Supplier")
	_check_user_can("read", "Purchase Invoice")
	_check_user_can("read", "Purchase Order")

	# Use frappe.get_list (permission-respecting) and aggregate in Python.
	pinvs = frappe.get_list(
		"Purchase Invoice",
		filters={"supplier": supplier, "docstatus": 1},
		fields=["name", "posting_date", "grand_total", "outstanding_amount", "status", "due_date"],
		order_by="posting_date desc",
		limit_page_length=10,
	)
	outstanding = sum((r.get("outstanding_amount") or 0) for r in pinvs)
	open_pos = frappe.get_list(
		"Purchase Order",
		filters={
			"supplier": supplier,
			"status": ["not in", ["Closed", "Cancelled", "Completed", "Delivered"]],
		},
		fields=["name", "transaction_date", "grand_total", "status", "schedule_date"],
		order_by="transaction_date desc",
		limit_page_length=10,
	)
	sup = frappe.db.get_value(
		"Supplier",
		supplier,
		["supplier_name", "supplier_group", "country", "mobile_no", "email_id"],
		as_dict=True,
	)
	return {
		"supplier": supplier,
		"details": sup,
		"outstanding_amount": float(outstanding or 0),
		"recent_invoices": pinvs,
		"open_purchase_orders": open_pos,
	}


def _h_pending_purchase_orders(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "pending_purchase_orders")
	_check_user_can("read", "Purchase Order")
	supplier = args.get("supplier")
	company = _resolve_company(args.get("company"))
	filters: dict = {
		"docstatus": 1,
		"status": ["not in", ["Closed", "Cancelled", "Completed", "Delivered"]],
	}
	if supplier:
		filters["supplier"] = supplier
	if company:
		filters["company"] = company
	rows = frappe.get_list(
		"Purchase Order",
		filters=filters,
		fields=[
			"name",
			"supplier",
			"transaction_date",
			"schedule_date",
			"grand_total",
			"per_received",
			"per_billed",
			"status",
			"company",
		],
		order_by="schedule_date asc",
		limit_page_length=min(int(args.get("limit") or 50), _max_rows()),
	)
	total = sum((r.get("grand_total") or 0) for r in rows)
	return {"count": len(rows), "total_value": float(total), "rows": rows}


# ---------------------------------------------------------------------------
# Selling
# ---------------------------------------------------------------------------


def _h_pending_sales_orders(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "pending_sales_orders")
	_check_user_can("read", "Sales Order")
	customer = args.get("customer")
	company = _resolve_company(args.get("company"))
	filters: dict = {
		"docstatus": 1,
		"status": ["not in", ["Closed", "Cancelled", "Completed"]],
	}
	if customer:
		filters["customer"] = customer
	if company:
		filters["company"] = company
	rows = frappe.get_list(
		"Sales Order",
		filters=filters,
		fields=[
			"name",
			"customer",
			"transaction_date",
			"delivery_date",
			"grand_total",
			"per_delivered",
			"per_billed",
			"status",
			"company",
		],
		order_by="delivery_date asc",
		limit_page_length=min(int(args.get("limit") or 50), _max_rows()),
	)
	total = sum((r.get("grand_total") or 0) for r in rows)
	return {"count": len(rows), "total_value": float(total), "rows": rows}


def _h_pending_quotations(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "pending_quotations")
	_check_user_can("read", "Quotation")
	customer = args.get("customer")
	filters: dict = {"docstatus": 1, "status": ["not in", ["Lost", "Cancelled", "Ordered"]]}
	if customer:
		filters["party_name"] = customer
	rows = frappe.get_list(
		"Quotation",
		filters=filters,
		fields=[
			"name",
			"party_name",
			"customer_name",
			"transaction_date",
			"valid_till",
			"grand_total",
			"status",
		],
		order_by="transaction_date desc",
		limit_page_length=min(int(args.get("limit") or 30), _max_rows()),
	)
	total = sum((r.get("grand_total") or 0) for r in rows)
	return {"count": len(rows), "total_value": float(total), "rows": rows}


def _h_delivery_status(args: dict, ctx: dict) -> dict:
	"""Pending Delivery Notes (post-SO, pre-billing) per customer."""
	_ensure_capability("allow_query_data", "delivery_status")
	_check_user_can("read", "Delivery Note")
	customer = args.get("customer")
	filters: dict = {"docstatus": 1, "status": ["not in", ["Cancelled", "Closed"]]}
	if customer:
		filters["customer"] = customer
	rows = frappe.get_list(
		"Delivery Note",
		filters=filters,
		fields=[
			"name",
			"customer",
			"posting_date",
			"grand_total",
			"per_billed",
			"status",
		],
		order_by="posting_date desc",
		limit_page_length=min(int(args.get("limit") or 30), _max_rows()),
	)
	return {"count": len(rows), "rows": rows}


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------


def _h_low_stock_items(args: dict, ctx: dict) -> dict:
	"""Items whose actual_qty falls below their re-order level."""
	_ensure_capability("allow_query_data", "low_stock_items")
	_check_user_can("read", "Item")
	_check_user_can("read", "Bin")
	_require_unrestricted("Bin", "low_stock_items")
	limit = min(int(args.get("limit") or 50), _max_rows())
	rows = frappe.db.sql(
		"""
		SELECT b.item_code, i.item_name, b.warehouse,
		       b.actual_qty, b.projected_qty, b.reserved_qty,
		       i.stock_uom,
		       COALESCE(MAX(ir.warehouse_reorder_level), 0) AS reorder_level
		FROM `tabBin` b
		JOIN `tabItem` i ON i.item_code = b.item_code
		LEFT JOIN `tabItem Reorder` ir ON ir.parent = i.name AND ir.warehouse = b.warehouse
		WHERE i.disabled = 0 AND i.is_stock_item = 1
		GROUP BY b.item_code, b.warehouse, i.item_name, b.actual_qty, b.projected_qty,
		         b.reserved_qty, i.stock_uom
		HAVING b.actual_qty <= reorder_level AND reorder_level > 0
		ORDER BY (reorder_level - b.actual_qty) DESC
		LIMIT %s
		""",
		(limit,),
		as_dict=True,
	)
	return {"count": len(rows), "rows": rows}


def _h_item_movement(args: dict, ctx: dict) -> dict:
	"""Recent Stock Ledger Entries for an item (read-only)."""
	_ensure_capability("allow_query_data", "item_movement")
	_check_user_can("read", "Stock Ledger Entry")
	_require_unrestricted("Stock Ledger Entry", "item_movement")
	item_code = args["item_code"]
	rows = frappe.get_list(
		"Stock Ledger Entry",
		filters={"item_code": item_code, "is_cancelled": 0},
		fields=[
			"name",
			"posting_date",
			"posting_time",
			"warehouse",
			"actual_qty",
			"qty_after_transaction",
			"voucher_type",
			"voucher_no",
		],
		order_by="posting_date desc, posting_time desc",
		limit_page_length=min(int(args.get("limit") or 30), _max_rows()),
	)
	return {"item_code": item_code, "count": len(rows), "rows": rows}


# ---------------------------------------------------------------------------
# Projects / Tasks
# ---------------------------------------------------------------------------


def _h_my_tasks(args: dict, ctx: dict) -> dict:
	"""Tasks assigned to (or owned by) the current user."""
	_ensure_capability("allow_query_data", "my_tasks")
	_check_user_can("read", "Task")
	user = frappe.session.user
	# Anything assigned via ToDo, plus tasks the user owns or created.
	# `_assign` is a JSON list, so use a LIKE match.
	filters: list = [
		["status", "not in", ["Completed", "Cancelled"]],
	]
	q = (args.get("status") or "").strip()
	if q:
		filters[0] = ["status", "=", q]
	rows = frappe.get_list(
		"Task",
		filters=filters,
		or_filters=[
			["_assign", "like", f"%{user}%"],
			["owner", "=", user],
		],
		fields=[
			"name",
			"subject",
			"status",
			"priority",
			"exp_start_date",
			"exp_end_date",
			"project",
			"progress",
		],
		order_by="exp_end_date asc",
		limit_page_length=min(int(args.get("limit") or 30), _max_rows()),
	)
	return {"user": user, "count": len(rows), "rows": rows}


def _h_project_summary(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "project_summary")
	_check_user_can("read", "Project")
	project = args["project"]
	p = frappe.db.get_value(
		"Project",
		project,
		[
			"name",
			"project_name",
			"status",
			"expected_start_date",
			"expected_end_date",
			"percent_complete",
			"total_billable_amount",
		],
		as_dict=True,
	)
	if not p:
		raise ValueError(f"Project '{project}' not found")
	tasks = frappe.get_list(
		"Task",
		filters={"project": project},
		fields=["name", "subject", "status", "exp_end_date", "progress"],
		order_by="exp_end_date asc",
		limit_page_length=50,
	)
	return {"project": p, "tasks": tasks, "task_count": len(tasks)}


# ---------------------------------------------------------------------------
# HR / HRMS
# ---------------------------------------------------------------------------


def _h_find_employee(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "find_employee")
	_check_user_can("read", "Employee")
	kw = (args.get("keyword") or "").strip()
	filters: dict = {"status": "Active"}
	or_filters = None
	if kw:
		or_filters = [
			["employee_name", "like", f"%{kw}%"],
			["name", "like", f"%{kw}%"],
			["user_id", "like", f"%{kw}%"],
		]
	rows = frappe.get_list(
		"Employee",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"employee_name",
			"designation",
			"department",
			"company",
			"user_id",
			"date_of_joining",
		],
		order_by="employee_name",
		limit_page_length=min(int(args.get("limit") or 20), _max_rows()),
	)
	return {"count": len(rows), "employees": rows}


def _h_pending_leave_applications(args: dict, ctx: dict) -> dict:
	_ensure_capability("allow_query_data", "pending_leave_applications")
	_check_user_can("read", "Leave Application")
	# Default: leaves where I'm the leave approver. If user is HR / System
	# Manager they will already see all (frappe.get_list applies perms).
	user = frappe.session.user
	approver = args.get("approver") or user
	filters: dict = {"status": "Open"}
	if approver:
		filters["leave_approver"] = approver
	rows = frappe.get_list(
		"Leave Application",
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"leave_type",
			"from_date",
			"to_date",
			"total_leave_days",
			"status",
			"posting_date",
		],
		order_by="posting_date desc",
		limit_page_length=min(int(args.get("limit") or 30), _max_rows()),
	)
	return {"approver": approver, "count": len(rows), "rows": rows}


def _h_my_attendance(args: dict, ctx: dict) -> dict:
	"""Attendance records for the current user (or for a specified employee
	if the user has HR Manager / System Manager role)."""
	_ensure_capability("allow_query_data", "my_attendance")
	_check_user_can("read", "Attendance")
	# Resolve target employee.
	user = frappe.session.user
	if args.get("employee"):
		# Only HR roles may look up other employees' attendance.
		roles = set(frappe.get_roles(user))
		if not (
			{"System Manager", "HR Manager", "HR User"} & roles
		):
			raise PermissionError("Only HR users can look up another employee's attendance.")
		emp = args["employee"]
	else:
		emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
		if not emp:
			raise ValueError("No Employee record linked to your user.")
	from_date = args.get("from_date") or frappe.utils.add_days(frappe.utils.today(), -30)
	to_date = args.get("to_date") or frappe.utils.today()
	rows = frappe.get_list(
		"Attendance",
		filters={
			"employee": emp,
			"attendance_date": ["between", [from_date, to_date]],
			"docstatus": 1,
		},
		fields=[
			"name",
			"attendance_date",
			"status",
			"working_hours",
			"in_time",
			"out_time",
			"shift",
		],
		order_by="attendance_date desc",
		limit_page_length=min(int(args.get("limit") or 60), _max_rows()),
	)
	summary = {"Present": 0, "Absent": 0, "Half Day": 0, "On Leave": 0, "Work From Home": 0}
	for r in rows:
		s = r.get("status") or ""
		if s in summary:
			summary[s] += 1
	return {
		"employee": emp,
		"from_date": str(from_date),
		"to_date": str(to_date),
		"count": len(rows),
		"summary": summary,
		"rows": rows,
	}


# ---------------------------------------------------------------------------
# Convenience / cross-module
# ---------------------------------------------------------------------------


def _h_recent_documents(args: dict, ctx: dict) -> dict:
	"""Recently created/edited documents the user can see, across one DocType."""
	_ensure_capability("allow_query_data", "recent_documents")
	doctype = args["doctype"]
	_ensure_doctype_allowed(doctype)
	_check_user_can("read", doctype)
	limit = min(int(args.get("limit") or 20), _max_rows())
	# `frappe.get_list` enforces perms.
	meta = frappe.get_meta(doctype)
	fields = ["name", "modified", "owner"]
	for f in ("title", "subject", "status", "customer", "supplier", "grand_total"):
		if meta.has_field(f):
			fields.append(f)
	rows = frappe.get_list(
		doctype,
		fields=fields,
		order_by="modified desc",
		limit_page_length=limit,
	)
	return {"doctype": doctype, "count": len(rows), "rows": rows}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_erpnext_tools():
	if not is_erpnext_installed():
		return

	register(
		Tool(
			name="list_companies",
			description="List Companies in ERPNext, returns the user's default company too.",
			parameters={"type": "object", "properties": {"limit": {"type": "integer", "default": 50}}},
			handler=_h_list_companies,
		)
	)
	register(
		Tool(
			name="find_customer",
			description="Search ERPNext Customers by keyword (matches customer_name).",
			parameters={
				"type": "object",
				"properties": {
					"keyword": {"type": "string"},
					"limit": {"type": "integer", "default": 20},
				},
			},
			handler=_h_find_customer,
		)
	)
	register(
		Tool(
			name="customer_summary",
			description=(
				"Return outstanding amount, recent invoices and open sales orders for a customer."
			),
			parameters={
				"type": "object",
				"properties": {"customer": {"type": "string"}},
				"required": ["customer"],
			},
			handler=_h_customer_summary,
		)
	)
	register(
		Tool(
			name="outstanding_invoices",
			description=(
				"List outstanding (unpaid) Sales/Purchase invoices, optionally filtered by party/company."
			),
			parameters={
				"type": "object",
				"properties": {
					"party_type": {"type": "string", "enum": ["Customer", "Supplier"], "default": "Customer"},
					"party": {"type": "string"},
					"company": {"type": "string"},
					"limit": {"type": "integer", "default": 50},
				},
			},
			handler=_h_outstanding_invoices,
		)
	)
	register(
		Tool(
			name="sales_summary",
			description="Aggregate sales totals by month for a company in an optional date range.",
			parameters={
				"type": "object",
				"properties": {
					"company": {"type": "string"},
					"from_date": {"type": "string", "description": "YYYY-MM-DD"},
					"to_date": {"type": "string", "description": "YYYY-MM-DD"},
				},
			},
			handler=_h_sales_summary,
		)
	)
	register(
		Tool(
			name="top_customers",
			description="Return top N customers by sales total in a date range.",
			parameters={
				"type": "object",
				"properties": {
					"company": {"type": "string"},
					"from_date": {"type": "string"},
					"to_date": {"type": "string"},
					"limit": {"type": "integer", "default": 10},
				},
			},
			handler=_h_top_customers,
		)
	)
	register(
		Tool(
			name="find_item",
			description="Search ERPNext Items by code/name/description.",
			parameters={
				"type": "object",
				"properties": {
					"keyword": {"type": "string"},
					"limit": {"type": "integer", "default": 20},
				},
			},
			handler=_h_find_item,
		)
	)
	register(
		Tool(
			name="stock_balance",
			description="Get current stock balance for an item across warehouses (or list all items in a warehouse).",
			parameters={
				"type": "object",
				"properties": {
					"item_code": {"type": "string"},
					"warehouse": {"type": "string"},
					"limit": {"type": "integer", "default": 50},
				},
			},
			handler=_h_stock_balance,
		)
	)
	register(
		Tool(
			name="financial_statement",
			description=(
				"Run a standard ERPNext financial statement (Profit and Loss, Balance Sheet, Cash Flow, Trial Balance) "
				"for a company and date range. Falls back to current fiscal year if dates not given."
			),
			parameters={
				"type": "object",
				"properties": {
					"statement": {
						"type": "string",
						"enum": [
							"Profit and Loss Statement",
							"Balance Sheet",
							"Cash Flow",
							"Trial Balance",
						],
						"default": "Profit and Loss Statement",
					},
					"company": {"type": "string"},
					"from_date": {"type": "string", "description": "YYYY-MM-DD"},
					"to_date": {"type": "string", "description": "YYYY-MM-DD"},
					"periodicity": {
						"type": "string",
						"enum": ["Monthly", "Quarterly", "Half-Yearly", "Yearly"],
						"default": "Yearly",
					},
				},
			},
			handler=_h_financial_statement,
		)
	)
	register(
		Tool(
			name="account_balance",
			description="Return GL balance for a chart-of-accounts account as of an optional date.",
			parameters={
				"type": "object",
				"properties": {
					"account": {"type": "string"},
					"company": {"type": "string"},
					"as_of": {"type": "string", "description": "YYYY-MM-DD"},
				},
				"required": ["account"],
			},
			handler=_h_account_balance,
		)
	)
	register(
		Tool(
			name="total_receivable",
			description=(
				"Return the total Accounts Receivable (debtors) balance from GL Entries. "
				"This is the canonical answer to 'how much do customers owe us' / 'total receivable'. "
				"Optionally scope by company and as-of date."
			),
			parameters={
				"type": "object",
				"properties": {
					"company": {"type": "string"},
					"as_of": {"type": "string", "description": "YYYY-MM-DD"},
				},
			},
			handler=_h_total_receivable,
		)
	)
	register(
		Tool(
			name="total_payable",
			description=(
				"Return the total Accounts Payable (creditors) balance from GL Entries. "
				"Canonical answer to 'how much do we owe suppliers' / 'total payable'."
			),
			parameters={
				"type": "object",
				"properties": {
					"company": {"type": "string"},
					"as_of": {"type": "string", "description": "YYYY-MM-DD"},
				},
			},
			handler=_h_total_payable,
		)
	)
	register(
		Tool(
			name="get_fiscal_year",
			description=(
				"Return a fiscal year with its from_date and to_date. "
				"Omit `year` to get the fiscal year that contains today's date. "
				"ALWAYS call this for 'this year' / 'last year' questions before constructing date ranges."
			),
			parameters={
				"type": "object",
				"properties": {
					"year": {
						"type": "string",
						"description": "Fiscal Year name like '2026-2027'. Omit for current fiscal year.",
					}
				},
			},
			handler=_h_get_fiscal_year,
		)
	)

	# --- Suppliers / Buying ---
	register(
		Tool(
			name="find_supplier",
			description="Search Suppliers by name keyword.",
			parameters={
				"type": "object",
				"properties": {
					"keyword": {"type": "string"},
					"limit": {"type": "integer", "default": 20},
				},
			},
			handler=_h_find_supplier,
		)
	)
	register(
		Tool(
			name="supplier_summary",
			description="360-view of a supplier: outstanding payable, recent invoices, open POs.",
			parameters={
				"type": "object",
				"properties": {"supplier": {"type": "string"}},
				"required": ["supplier"],
			},
			handler=_h_supplier_summary,
		)
	)
	register(
		Tool(
			name="pending_purchase_orders",
			description="List Purchase Orders that are not yet received/closed/cancelled.",
			parameters={
				"type": "object",
				"properties": {
					"supplier": {"type": "string"},
					"company": {"type": "string"},
					"limit": {"type": "integer", "default": 50},
				},
			},
			handler=_h_pending_purchase_orders,
		)
	)

	# --- Selling extras ---
	register(
		Tool(
			name="pending_sales_orders",
			description="List Sales Orders that are not yet delivered / closed / cancelled.",
			parameters={
				"type": "object",
				"properties": {
					"customer": {"type": "string"},
					"company": {"type": "string"},
					"limit": {"type": "integer", "default": 50},
				},
			},
			handler=_h_pending_sales_orders,
		)
	)
	register(
		Tool(
			name="pending_quotations",
			description="List submitted Quotations that are still open (not Lost / Cancelled / Ordered).",
			parameters={
				"type": "object",
				"properties": {
					"customer": {"type": "string"},
					"limit": {"type": "integer", "default": 30},
				},
			},
			handler=_h_pending_quotations,
		)
	)
	register(
		Tool(
			name="delivery_status",
			description="Recent Delivery Notes with billing % — useful for tracking pending invoicing.",
			parameters={
				"type": "object",
				"properties": {
					"customer": {"type": "string"},
					"limit": {"type": "integer", "default": 30},
				},
			},
			handler=_h_delivery_status,
		)
	)

	# --- Stock extras ---
	register(
		Tool(
			name="low_stock_items",
			description="Items whose actual_qty is at/below their warehouse re-order level.",
			parameters={
				"type": "object",
				"properties": {"limit": {"type": "integer", "default": 50}},
			},
			handler=_h_low_stock_items,
		)
	)
	register(
		Tool(
			name="item_movement",
			description="Recent stock ledger movements for a single item across warehouses.",
			parameters={
				"type": "object",
				"properties": {
					"item_code": {"type": "string"},
					"limit": {"type": "integer", "default": 30},
				},
				"required": ["item_code"],
			},
			handler=_h_item_movement,
		)
	)

	# --- Project / Task ---
	register(
		Tool(
			name="my_tasks",
			description="Tasks assigned to (or owned by) the current user, optionally filtered by status.",
			parameters={
				"type": "object",
				"properties": {
					"status": {"type": "string"},
					"limit": {"type": "integer", "default": 30},
				},
			},
			handler=_h_my_tasks,
		)
	)
	register(
		Tool(
			name="project_summary",
			description="Snapshot of a Project including its tasks and progress.",
			parameters={
				"type": "object",
				"properties": {"project": {"type": "string"}},
				"required": ["project"],
			},
			handler=_h_project_summary,
		)
	)

	# --- HR / HRMS ---
	if "hrms" in (frappe.get_installed_apps() or []):
		register(
			Tool(
				name="find_employee",
				description="Search active Employees by name / id / email.",
				parameters={
					"type": "object",
					"properties": {
						"keyword": {"type": "string"},
						"limit": {"type": "integer", "default": 20},
					},
				},
				handler=_h_find_employee,
			)
		)
		register(
			Tool(
				name="pending_leave_applications",
				description=(
					"Leave Applications still in 'Open' status awaiting approval. Defaults to "
					"the current user as approver."
				),
				parameters={
					"type": "object",
					"properties": {
						"approver": {"type": "string"},
						"limit": {"type": "integer", "default": 30},
					},
				},
				handler=_h_pending_leave_applications,
			)
		)
		register(
			Tool(
				name="my_attendance",
				description=(
					"Attendance summary for the current user (last 30 days by default). "
					"HR Managers may pass `employee` to look up another employee."
				),
				parameters={
					"type": "object",
					"properties": {
						"employee": {"type": "string"},
						"from_date": {"type": "string", "description": "YYYY-MM-DD"},
						"to_date": {"type": "string", "description": "YYYY-MM-DD"},
						"limit": {"type": "integer", "default": 60},
					},
				},
				handler=_h_my_attendance,
			)
		)

	# --- Convenience ---
	register(
		Tool(
			name="recent_documents",
			description=(
				"Recently created or modified documents of any DocType the user can read. "
				"Useful for 'show me latest <X>' style questions."
			),
			parameters={
				"type": "object",
				"properties": {
					"doctype": {"type": "string"},
					"limit": {"type": "integer", "default": 20},
				},
				"required": ["doctype"],
			},
			handler=_h_recent_documents,
		)
	)


# Register on import (no-op when ERPNext is missing)
register_erpnext_tools()
