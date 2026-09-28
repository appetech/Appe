import frappe
from frappe.utils import cint, flt, get_url


CATEGORY_FIELDS = [
	"name",
	"category",
	"title",
	"subtitle",
	"description",
	"icon",
	"background_image",
	"status",
	"show_in_home_screen",
	"color_1",
	"color_2",
	"is_group",
	"parent_appe_category",
	"sequence_id",
]

ITEM_FIELDS = [
	"name",
	"item_code",
	"item_name",
	"subtitle",
	"description",
	"category",
	"brand",
	"uom",
	"image",
	"video",
	"mrp",
	"rate",
	"discount_percentage",
	"in_stock",
	"stock_qty",
	"show_in_home_screen",
	"is_featured",
	"sequence_id",
	"status",
]


@frappe.whitelist()
def get_shop_home():
	"""Home payload for Flutter EcommerceScreen."""
	try:
		categories = _get_categories({"status": "Active", "show_in_home_screen": 1})
		featured_items = _get_items({"status": "Active", "is_featured": 1})
		home_items = _get_items({"status": "Active", "show_in_home_screen": 1})
		banners = []
		for category in categories:
			for banner in category.get("banner") or []:
				banners.append(
					{
						"image": banner,
						"category": category.get("name"),
						"title": category.get("title"),
					}
				)

		return _ok(
			{
				"categories": categories,
				"banners": banners,
				"featured_items": featured_items,
				"home_items": home_items,
			}
		)
	except Exception as e:
		frappe.log_error("Appe Shop Home Error", frappe.get_traceback())
		return _fail(e)


@frappe.whitelist()
def get_categories(parent=None, show_in_home_screen=None):
	"""Flat category list for Flutter CategoryScreen / ProductScreen."""
	try:
		filters = {"status": "Active"}
		if parent:
			filters["parent_appe_category"] = parent
		if cint(show_in_home_screen):
			filters["show_in_home_screen"] = 1

		return _ok(_get_categories(filters))
	except Exception as e:
		frappe.log_error("Appe Shop Categories Error", frappe.get_traceback())
		return _fail(e)


@frappe.whitelist()
def get_items(category=None, search=None, featured=None, show_in_home_screen=None, limit=50, offset=0):
	"""Item list for Flutter ProductScreen / search."""
	try:
		filters = {"status": "Active"}
		if category:
			filters["category"] = category
		if cint(featured):
			filters["is_featured"] = 1
		if cint(show_in_home_screen):
			filters["show_in_home_screen"] = 1

		or_filters = None
		if search:
			like = f"%{search}%"
			or_filters = [
				["item_name", "like", like],
				["item_code", "like", like],
				["brand", "like", like],
			]

		return _ok(
			_get_items(
				filters,
				or_filters=or_filters,
				limit=cint(limit) or 50,
				offset=cint(offset),
			)
		)
	except Exception as e:
		frappe.log_error("Appe Shop Items Error", frappe.get_traceback())
		return _fail(e)


@frappe.whitelist()
def get_item_details(item_code=None, name=None):
	"""Single item payload for Flutter product detail."""
	try:
		item_name = item_code or name
		if not item_name:
			frappe.throw("item_code is required")

		filters = {"status": "Active"}
		if frappe.db.exists("Appe Item", item_name):
			filters["name"] = item_name
		else:
			filters["item_code"] = item_name

		items = _get_items(filters, limit=1, with_gallery=True)
		if not items:
			frappe.throw("Item not found")

		return _ok(items[0])
	except Exception as e:
		frappe.log_error("Appe Shop Item Details Error", frappe.get_traceback())
		return _fail(e)


def _ok(data):
	payload = {"status": True, "data": data}
	frappe.response.message = payload
	return payload


def _fail(error):
	payload = {"status": False, "data": str(error)}
	frappe.response.message = payload
	return payload


def _get_categories(filters):
	rows = frappe.get_all(
		"Appe Category",
		filters=filters,
		fields=CATEGORY_FIELDS,
		order_by="sequence_id asc, category asc",
		ignore_permissions=True,
	)
	return [_format_category(row) for row in rows]


def _get_items(filters, or_filters=None, limit=50, offset=0, with_gallery=False):
	rows = frappe.get_all(
		"Appe Item",
		filters=filters,
		or_filters=or_filters,
		fields=ITEM_FIELDS,
		limit_page_length=limit,
		limit_start=offset,
		order_by="sequence_id asc, modified desc",
		ignore_permissions=True,
	)
	return [_format_item(row, with_gallery=with_gallery) for row in rows]


def _format_category(row):
	return {
		"name": row.name,
		"category": row.category,
		"title": row.title or row.category,
		"subtitle": row.subtitle or "",
		"description": row.description or "",
		"icon": _abs_url(row.icon),
		"background_image": _abs_url(row.background_image),
		"banner": _category_banners(row.name, row.icon, row.background_image),
		"status": row.status,
		"show_in_home_screen": cint(row.show_in_home_screen),
		"color_1": row.color_1 or "",
		"color_2": row.color_2 or "",
		"is_group": cint(row.is_group),
		"parent_appe_category": row.parent_appe_category or "",
		"sequence_id": cint(row.sequence_id),
	}


def _format_item(row, with_gallery=False):
	images = _item_images(row.name, row.image) if with_gallery else [_abs_url(row.image)] if row.image else []
	rate = flt(row.rate)
	mrp = flt(row.mrp) or rate
	videos = [_abs_url(row.video)] if row.video else []
	return {
		"name": row.name,
		"item_code": row.item_code or row.name,
		"item_name": row.item_name,
		"subtitle": row.subtitle or "",
		"description": row.description or "",
		"category": row.category or "",
		"item_group": row.category or "",
		"brand": row.brand or "",
		"uom": row.uom or "",
		"image": _abs_url(row.image) or (images[0] if images else ""),
		"images": [img for img in images if img],
		"videos": videos,
		"price": mrp,
		"mrp": mrp,
		"rate": rate,
		"net_rate": rate,
		"discount_percentage": flt(row.discount_percentage),
		"in_stock": cint(row.in_stock),
		"stock_qty": flt(row.stock_qty),
		"show_in_home_screen": cint(row.show_in_home_screen),
		"is_featured": cint(row.is_featured),
		"sequence_id": cint(row.sequence_id),
		"status": row.status,
	}


def _item_images(item_name, fallback=None):
	rows = frappe.get_all(
		"Appe Item Image",
		filters={"parent": item_name, "parenttype": "Appe Item"},
		fields=["image", "is_primary", "idx"],
		order_by="is_primary desc, idx asc",
		ignore_permissions=True,
	)
	images = [_abs_url(row.image) for row in rows if row.image]
	fallback_url = _abs_url(fallback)
	if fallback_url and fallback_url not in images:
		images.insert(0, fallback_url)
	return images


def _category_banners(category_name, icon=None, background_image=None):
	files = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Appe Category",
			"attached_to_name": category_name,
			"is_folder": 0,
		},
		fields=["file_url"],
		ignore_permissions=True,
	)
	skip = {_abs_url(icon), _abs_url(background_image), ""}
	banners = []
	for row in files:
		url = _abs_url(row.file_url)
		if url and url not in skip and url not in banners:
			banners.append(url)
	return banners


def _abs_url(path):
	if not path:
		return ""
	if path.startswith("http://") or path.startswith("https://"):
		return path
	return get_url(path)
