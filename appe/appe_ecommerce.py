import json
import re

import frappe
from frappe import _

GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
INDIA_STATES = (
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
)


ADDRESS_TYPES = (
    "Billing",
    "Shipping",
    "Office",
    "Personal",
    "Plant",
    "Postal",
    "Shop",
    "Subsidiary",
    "Warehouse",
    "Current",
    "Permanent",
    "Other",
)


def _user():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Not logged in"), frappe.AuthenticationError)
    return user


def _fields(doctype, wanted):
    meta = frappe.get_meta(doctype)
    allowed = {df.fieldname for df in meta.fields}
    allowed.update({"name", "owner", "creation", "modified", "docstatus"})
    return [field for field in wanted if field in allowed]


def _rows(doctype, fields, filters=None, order_by="modified desc", limit=500, start=0):
    if not frappe.db.exists("DocType", doctype):
        return []
    safe = _fields(doctype, fields)
    if "name" not in safe:
        safe.insert(0, "name")
    try:
        offset = int(start or 0)
    except Exception:
        offset = 0
    if offset < 0:
        offset = 0
    return frappe.get_all(
        doctype,
        fields=safe,
        filters=filters or {},
        order_by=order_by,
        limit_start=offset,
        limit_page_length=limit,
        ignore_permissions=True,
    )


def _doc(doctype, name):
    if not frappe.db.exists(doctype, name):
        frappe.throw(_("{0} {1} not found").format(doctype, name), frappe.DoesNotExistError)
    doc = frappe.get_doc(doctype, name)
    doc.flags.ignore_permissions = True
    return doc


def _erpnext_installed():
    try:
        return "erpnext" in frappe.get_installed_apps()
    except Exception:
        return False


def _ensure_custom_field(doctype, fieldname, label, fieldtype, **opts):
    meta = frappe.get_meta(doctype)
    if meta.has_field(fieldname):
        return
    frappe.get_doc(
        {
            "doctype": "Custom Field",
            "dt": doctype,
            "fieldname": fieldname,
            "label": label,
            "fieldtype": fieldtype,
            "insert_after": opts.get("insert_after") or "image",
            "options": opts.get("options"),
            "default": opts.get("default"),
        }
    ).insert(ignore_permissions=True)


def _ensure_description_tab_doctype():
    if frappe.db.exists("DocType", "Appe Item Description Tab"):
        return
    frappe.get_doc(
        {
            "doctype": "DocType",
            "name": "Appe Item Description Tab",
            "module": "Custom",
            "custom": 1,
            "istable": 1,
            "editable_grid": 1,
            "fields": [
                {
                    "fieldname": "tab_name",
                    "label": "Tab Name",
                    "fieldtype": "Data",
                    "in_list_view": 1,
                },
                {
                    "fieldname": "description",
                    "label": "Description",
                    "fieldtype": "Text Editor",
                },
                {
                    "fieldname": "active",
                    "label": "Active",
                    "fieldtype": "Check",
                    "default": "1",
                    "in_list_view": 1,
                },
            ],
        }
    ).insert(ignore_permissions=True)


def _ensure_erpnext_fields():
    """Item Group stands in for Appe Category, Item for Appe Item."""
    if not _erpnext_installed():
        return
    if getattr(frappe.local, "appe_erp_fields_ready", False):
        return

    for field in (
        ("subtitle", "Subtitle", "Data", {}),
        ("status", "Status", "Select", {"options": "Active\nInactive", "default": "Active"}),
        ("sequence_id", "Sequence", "Int", {"default": "0"}),
        ("show_in_home_screen", "Show in Home Screen", "Check", {"default": "0"}),
        ("show_in_bestsellers", "Show in Bestsellers", "Check", {"default": "0"}),
        ("icon", "Icon", "Attach Image", {}),
        ("background_image", "Background Image", "Attach Image", {}),
        ("banner", "Banner", "Attach Image", {}),
        ("color_1", "Color 1", "Color", {}),
        ("color_2", "Color 2", "Color", {}),
        ("search_hint", "Search Hint", "Data", {}),
        ("extra_count_label", "Extra Count Label", "Data", {}),
    ):
        _ensure_custom_field("Item Group", field[0], field[1], field[2], **field[3])

    for field in (
        ("subtitle", "Subtitle", "Data", {}),
        ("status", "Status", "Select", {"options": "Active\nInactive", "default": "Active"}),
        ("mrp", "MRP", "Currency", {}),
        ("discount_percentage", "Discount Percentage", "Float", {}),
        ("in_stock", "In Stock", "Check", {"default": "1"}),
        ("show_in_home_screen", "Show in Home Screen", "Check", {"default": "0"}),
        ("is_featured", "Featured", "Check", {"default": "0"}),
        ("sequence_id", "Sequence", "Int", {"default": "0"}),
        ("video", "Video", "Attach", {}),
        ("pack_info", "Pack Info", "Data", {}),
        ("tags", "Tags", "Small Text", {}),
        ("delivery_mins", "Delivery Minutes", "Data", {}),
    ):
        _ensure_custom_field("Item", field[0], field[1], field[2], insert_after="item_name", **field[3])

    _ensure_description_tab_doctype()
    _ensure_custom_field(
        "Item",
        "description_tabs",
        "Description Tabs",
        "Table",
        insert_after="description",
        options="Appe Item Description Tab",
    )
    _ensure_custom_field(
        "Quotation",
        "cancel_reason",
        "Cancel Reason",
        "Small Text",
        insert_after="customer_name",
    )
    frappe.db.commit()
    frappe.clear_cache(doctype="Item Group")
    frappe.clear_cache(doctype="Item")
    frappe.clear_cache(doctype="Quotation")
    frappe.local.appe_erp_fields_ready = True


def _map_item_group(row):
    parent = (row.get("parent_item_group") or "").strip()
    if parent in ("All Item Groups", "All Item Group", "Categories"):
        parent = ""
    title = (row.get("item_group_name") or row.get("name") or "").strip()
    return {
        "name": row.get("name"),
        "category": title,
        "title": title,
        "subtitle": row.get("subtitle") or "",
        "description": row.get("description") or "",
        "status": row.get("status") or "Active",
        "sequence_id": row.get("sequence_id") or 0,
        "show_in_home_screen": row.get("show_in_home_screen") or 0,
        "show_in_bestsellers": row.get("show_in_bestsellers") or 0,
        "is_group": row.get("is_group") or 0,
        "parent_appe_category": parent,
        "icon": row.get("icon") or row.get("image") or "",
        "background_image": row.get("background_image") or "",
        "banner": row.get("banner") or "",
        "color_1": row.get("color_1") or "",
        "color_2": row.get("color_2") or "",
        "search_hint": row.get("search_hint") or "",
        "extra_count_label": row.get("extra_count_label") or "",
    }


def _selling_rate_map(item_codes):
    if not item_codes or not frappe.db.exists("DocType", "Item Price"):
        return {}
    rows = frappe.get_all(
        "Item Price",
        filters={"item_code": ["in", item_codes], "selling": 1},
        fields=["item_code", "price_list_rate"],
        order_by="modified desc",
        limit_page_length=max(len(item_codes) * 4, 20),
        ignore_permissions=True,
    )
    rates = {}
    for row in rows:
        rates.setdefault(row.item_code, row.price_list_rate)
    return rates


def _map_item(row, rate=None, detail=None):
    disabled = int(row.get("disabled") or 0)
    status = row.get("status") or ("Inactive" if disabled else "Active")
    price = row.get("standard_rate") or 0
    if rate is not None:
        price = rate
    mrp = row.get("mrp") or price
    payload = {
        "name": row.get("name") or row.get("item_code"),
        "item_code": row.get("item_code") or row.get("name"),
        "item_name": row.get("item_name") or row.get("name"),
        "subtitle": row.get("subtitle") or "",
        "brand": row.get("brand") or "",
        "category": row.get("item_group") or "",
        "status": status,
        "mrp": mrp,
        "rate": price,
        "discount_percentage": row.get("discount_percentage") or 0,
        "uom": row.get("stock_uom") or "",
        "in_stock": 1 if row.get("in_stock") in (None, "") else row.get("in_stock"),
        "stock_qty": row.get("stock_qty") or 0,
        "show_in_home_screen": row.get("show_in_home_screen") or 0,
        "is_featured": row.get("is_featured") or 0,
        "sequence_id": row.get("sequence_id") or 0,
        "image": row.get("image") or "",
        "video": row.get("video") or "",
        "description": row.get("description") or "",
        "pack_info": row.get("pack_info") or "",
        "tags": row.get("tags") or "",
        "delivery_mins": row.get("delivery_mins") or "",
    }
    if detail is not None:
        payload["description_tabs"] = [
            {
                "tab_name": tab.get("tab_name"),
                "description": tab.get("description"),
                "active": tab.get("active"),
                "idx": tab.get("idx"),
            }
            for tab in (detail.get("description_tabs") or [])
        ]
        payload["uoms"] = [
            {
                "uom": uom.get("uom"),
                "conversion_factor": uom.get("conversion_factor") or 1,
                "is_default": 1 if uom.get("uom") == detail.get("stock_uom") else 0,
            }
            for uom in (detail.get("uoms") or [])
            if uom.get("uom")
        ]
        # payload["images"] = []
        files = _item_files(row.get("name"))
        images = [row.get("image")] if row.get("image") else []
        for f in files:
            url = (f.get("file_url") or "").strip()
            if url and url not in images and url.lower().split("?")[0].endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")):
                images.append(url)
        payload["images"] = images
        payload["files"] = files
    return payload


def _item_files(name):
    if not name:
        return []
    return frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Item", "attached_to_name": name, "is_private": 0},
        fields=["file_url", "file_name"],
        order_by="creation asc",
        limit_page_length=0,
        ignore_permissions=True,
    )



def _company():
    company = frappe.defaults.get_user_default("Company")
    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        company = frappe.db.get_value("Company", {}, "name")
    if not company:
        frappe.throw(_("Set a Company in ERPNext before placing an order"))
    return company


def _leaf(doctype):
    name = frappe.db.get_value(doctype, {"is_group": 0}, "name")
    if name:
        return name
    return frappe.db.get_value(doctype, {}, "name")


def _customer_for(user):
    parent = frappe.db.get_value(
        "Portal User",
        {"parenttype": "Customer", "user": user},
        "parent",
    )
    if parent and frappe.db.exists("Customer", parent):
        return _doc("Customer", parent)
    name = frappe.db.get_value("Customer", {"email_id": user}, "name")
    if name:
        return _doc("Customer", name)
    full_name = frappe.db.get_value("User", user, "full_name") or user
    doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": full_name,
            "customer_type": "Individual",
            "customer_group": _leaf("Customer Group"),
            "territory": _leaf("Territory"),
            "email_id": user if "@" in (user or "") else "",
            "portal_users": [{"user": user}],
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc


def _customer_address(customer_name):
    rows = _customer_addresses(customer_name)
    if not rows:
        return None
    return _doc("Address", rows[0]["name"])


def _address_record(name):
    fields = [
        "name",
        "address_title",
        "address_type",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "pincode",
        "country",
        "phone",
        "email_id",
        "is_primary_address",
        "is_shipping_address",
    ]
    if frappe.get_meta("Address").has_field("gstin"):
        fields.append("gstin")
    return frappe.db.get_value("Address", name, fields, as_dict=True)


def _customer_addresses(customer_name):
    parents = frappe.get_all(
        "Dynamic Link",
        filters={"link_doctype": "Customer", "link_name": customer_name, "parenttype": "Address"},
        pluck="parent",
        ignore_permissions=True,
    )
    seen = []
    rows = []
    for name in parents:
        if not name or name in seen:
            continue
        seen.append(name)
        record = _address_record(name)
        if record:
            rows.append(_map_address(record))
    rows.sort(key=lambda row: (0 if row.get("is_primary") or row.get("is_shipping") else 1, row.get("name") or ""))
    return rows


def _map_address(address):
    return {
        "name": address.name,
        "title": address.get("address_title") or "",
        "address_type": address.get("address_type") or "",
        "address_line1": address.get("address_line1") or "",
        "address_line2": address.get("address_line2") or "",
        "city": address.get("city") or "",
        "state": address.get("state") or "",
        "pincode": address.get("pincode") or "",
        "country": address.get("country") or "",
        "phone": address.get("phone") or "",
        "email": address.get("email_id") or "",
        "gstin": address.get("gstin") or "",
        "is_primary": int(address.get("is_primary_address") or 0),
        "is_shipping": int(address.get("is_shipping_address") or 0),
    }


def _clean_address_type(value, fallback="Shipping"):
    text = (value or "").strip()
    if not text:
        return fallback
    match = next((name for name in ADDRESS_TYPES if name.lower() == text.lower()), "")
    if not match:
        frappe.throw(_("Select an address type"))
    return match


def _clean_gstin(gstin, required=False):
    value = re.sub(r"\s+", "", (gstin or "")).upper()
    if not value:
        if required:
            frappe.throw(_("Enter GSTIN"))
        return ""
    if not GSTIN_PATTERN.fullmatch(value):
        frappe.throw(_("Enter a valid 15-character GSTIN"))
    return value


def _clean_state(state):
    value = (state or "").strip()
    if not value:
        frappe.throw(_("Select a state"))
    match = next((name for name in INDIA_STATES if name.lower() == value.lower()), "")
    if not match:
        frappe.throw(_("Select a state"))
    return match


def _apply_customer_gstin(customer, gstin):
    if customer.meta.has_field("gstin"):
        customer.gstin = gstin or ""
    if gstin and customer.meta.has_field("tax_id"):
        customer.tax_id = gstin
    if customer.meta.has_field("gst_category"):
        customer.gst_category = "Registered Regular" if gstin else (customer.get("gst_category") or "Unregistered")


def _insert_customer_address(customer, address_line1, city, state, pincode="", address_line2="", phone="", email="", gstin="", address_type="Shipping", title=""):
    meta = frappe.get_meta("Address")
    country = frappe.db.get_value("Country", "India", "name") or frappe.db.get_default("country") or "India"
    existing = _customer_addresses(customer.name)
    data = {
        "doctype": "Address",
        "address_title": (title or customer.customer_name or customer.name)[:140],
        "address_type": address_type or "Shipping",
        "address_line1": (address_line1 or customer.customer_name or "-")[:140],
        "address_line2": address_line2 or "",
        "city": (city or state or "-")[:140],
        "state": state or "",
        "pincode": pincode or "",
        "country": country,
        "phone": phone or "",
        "email_id": email or customer.get("email_id") or "",
        "is_primary_address": 0 if existing else 1,
        "is_shipping_address": 1,
        "links": [{"link_doctype": "Customer", "link_name": customer.name}],
    }
    if gstin and meta.has_field("gstin"):
        data["gstin"] = gstin
    if meta.has_field("gst_category"):
        data["gst_category"] = "Registered Regular" if gstin else "Unregistered"
    doc = frappe.get_doc(data)
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    return doc


def _profile_payload(user, customer):
    addresses = _customer_addresses(customer.name)
    address = addresses[0] if addresses else None
    line = ""
    city = ""
    pincode = ""
    state = ""
    gstin = customer.get("gstin") or customer.get("tax_id") or ""
    if address:
        line = " ".join(
            part
            for part in [address.get("address_line1") or "", address.get("address_line2") or ""]
            if part
        ).strip()
        city = address.get("city") or ""
        pincode = address.get("pincode") or ""
        state = address.get("state") or ""
        gstin = address.get("gstin") or gstin
    return {
        "name": customer.name,
        "user": user,
        "full_name": customer.get("customer_name") or "",
        "phone": customer.get("mobile_no") or customer.get("mobile_number") or "",
        "email": customer.get("email_id") or user,
        "address": line,
        "city": city,
        "state": state,
        "pincode": pincode,
        "gstin": gstin,
        "addresses": addresses,
    }


def _app_order_status(doc):
    status = (doc.get("status") or "").strip()
    docstatus = int(doc.get("docstatus") or 0)
    if docstatus == 2 or status in ("Cancelled", "Lost", "Expired"):
        return "Cancelled"
    if status in ("Completed", "Closed", "Ordered", "Partially Ordered"):
        return "Confirmed" if status in ("Ordered", "Partially Ordered") else "Delivered"
    if status in ("To Deliver", "To Bill", "To Deliver and Bill", "Replied"):
        return "Confirmed"
    return "Placed"


def _map_sales_order(doc, with_items=False):
    payload = {
        "name": doc.name,
        "user": frappe.session.user,
        "customer_name": doc.get("customer_name") or "",
        "status": _app_order_status(doc),
        "delivery_address": doc.get("shipping_address") or doc.get("address_display") or "",
        "total_qty": doc.get("total_qty") or 0,
        "grand_total": doc.get("grand_total") or 0,
        "notes": doc.get("terms") or "",
        "cancel_reason": doc.get("cancel_reason") or "",
        "creation": doc.get("creation"),
        "modified": doc.get("modified"),
    }
    if with_items:
        payload["items"] = [
            {
                "item": row.get("item_code"),
                "item_name": row.get("item_name"),
                "uom": row.get("uom") or row.get("stock_uom") or "",
                "qty": row.get("qty"),
                "rate": row.get("rate"),
                "amount": row.get("amount"),
            }
            for row in (doc.get("items") or [])
        ]
    return payload


@frappe.whitelist(allow_guest=True)
def get_categories():
    if _erpnext_installed():
        _ensure_erpnext_fields()
        rows = _rows(
            "Item Group",
            [
                "name",
                "item_group_name",
                "parent_item_group",
                "is_group",
                "image",
                "description",
                "subtitle",
                "status",
                "sequence_id",
                "show_in_home_screen",
                "show_in_bestsellers",
                "icon",
                "background_image",
                "banner",
                "color_1",
                "color_2",
                "search_hint",
                "extra_count_label",
            ],
            filters={"parent_item_group": "Categories"},
            order_by="sequence_id asc, item_group_name asc",
        )
        mapped = []
        for row in rows:
            if (row.get("name") or "") in ("Categories", "All Item Groups", "All Item Group"):
                continue
            if (row.get("status") or "Active") != "Active":
                continue
            mapped.append(_map_item_group(row))
        return mapped
    return _rows(
        "Appe Category",
        [
            "name",
            "category",
            "title",
            "subtitle",
            "description",
            "status",
            "sequence_id",
            "show_in_home_screen",
            "show_in_bestsellers",
            "is_group",
            "parent_appe_category",
            "icon",
            "background_image",
            # "banner",
            "color_1",
            "color_2",
            "search_hint",
            "extra_count_label",
        ],
        filters={"status": "Active"},
        order_by="sequence_id asc",
    )


_ITEM_GROUP_FIELDS = [
    "name",
    "item_group_name",
    "parent_item_group",
    "is_group",
    "image",
    "description",
    "subtitle",
    "status",
    "sequence_id",
    "show_in_home_screen",
    "show_in_bestsellers",
    "icon",
    "background_image",
    "banner",
    "color_1",
    "color_2",
    "search_hint",
    "extra_count_label",
    "lft",
    "rgt",
]

_ERP_ITEM_FIELDS = [
    "name",
    "item_code",
    "item_name",
    "item_group",
    "brand",
    "stock_uom",
    "disabled",
    "standard_rate",
    "image",
    "description",
    "subtitle",
    "status",
    "mrp",
    "discount_percentage",
    "in_stock",
    "show_in_home_screen",
    "is_featured",
    "sequence_id",
    "video",
    "pack_info",
    "tags",
    "delivery_mins",
    "has_variants",
]


def _descendant_item_groups(name):
    """Child groups by parent link. Nested-set lft/rgt is only a backup."""
    rows = []
    seen = {name}
    frontier = [name]
    while frontier:
        current = frontier.pop(0)
        kids = _rows(
            "Item Group",
            _ITEM_GROUP_FIELDS,
            filters={"parent_item_group": current},
            order_by="item_group_name asc",
        )
        for kid in kids:
            kid_name = kid.get("name")
            if not kid_name or kid_name in seen:
                continue
            seen.add(kid_name)
            rows.append(kid)
            frontier.append(kid_name)
    if not rows:
        parent = _doc("Item Group", name)
        lft = int(parent.get("lft") or 0)
        rgt = int(parent.get("rgt") or 0)
        if rgt > lft + 1:
            for row in _rows(
                "Item Group",
                _ITEM_GROUP_FIELDS,
                filters={"lft": [">", lft], "rgt": ["<", rgt]},
                order_by="lft asc",
            ):
                kid_name = row.get("name")
                if not kid_name or kid_name in seen:
                    continue
                seen.add(kid_name)
                rows.append(row)
    mapped = []
    for row in rows:
        if (row.get("name") or "") in ("All Item Groups", "All Item Group", "Categories"):
            continue
        if (row.get("status") or "Active") != "Active":
            continue
        mapped.append(_map_item_group(row))
    return mapped


def _item_group_tree(name, seen):
    """Nested item groups under [name]. Each node includes its own children."""
    nodes = []
    kids = _rows(
        "Item Group",
        _ITEM_GROUP_FIELDS,
        filters={"parent_item_group": name},
        order_by="sequence_id asc, item_group_name asc",
    )
    for kid in kids:
        kid_name = kid.get("name") or ""
        if not kid_name or kid_name in seen:
            continue
        if kid_name in ("Categories", "All Item Groups", "All Item Group"):
            continue
        if (kid.get("status") or "Active") != "Active":
            continue
        seen.add(kid_name)
        node = _map_item_group(kid)
        node["children"] = _item_group_tree(kid_name, seen)
        nodes.append(node)
    return nodes


def _appe_category_tree(name, by_parent, seen):
    nodes = []
    for row in by_parent.get(name, []):
        child_name = row.get("name") or ""
        if not child_name or child_name in seen:
            continue
        seen.add(child_name)
        node = dict(row)
        node["children"] = _appe_category_tree(child_name, by_parent, seen)
        nodes.append(node)
    return nodes


@frappe.whitelist(allow_guest=True)
def get_category_groups():
    """Categories screen. Each category includes the groups nested under it."""
    if _erpnext_installed():
        _ensure_erpnext_fields()
        seen = set()
        sections = []
        for cat in get_categories():
            name = cat.get("name") or ""
            if name:
                seen.add(name)
            sections.append(
                {
                    "category": cat,
                    "children": _item_group_tree(name, seen) if name else [],
                }
            )
        return sections

    rows = _rows(
        "Appe Category",
        [
            "name",
            "category",
            "title",
            "subtitle",
            "description",
            "status",
            "sequence_id",
            "show_in_home_screen",
            "show_in_bestsellers",
            "is_group",
            "parent_appe_category",
            "icon",
            "background_image",
            "color_1",
            "color_2",
            "search_hint",
            "extra_count_label",
        ],
        filters={"status": "Active"},
        order_by="sequence_id asc",
    )
    by_parent = {}
    tops = []
    for row in rows:
        parent = (row.get("parent_appe_category") or "").strip()
        if not parent:
            tops.append(row)
        else:
            by_parent.setdefault(parent, []).append(row)
    seen = set()
    sections = []
    for row in tops:
        name = row.get("name") or ""
        if name:
            seen.add(name)
        sections.append(
            {
                "category": row,
                "children": _appe_category_tree(name, by_parent, seen) if name else [],
            }
        )
    return sections


_APPE_ITEM_FIELDS = [
    "name",
    "item_code",
    "item_name",
    "subtitle",
    "brand",
    "category",
    "status",
    "mrp",
    "rate",
    "discount_percentage",
    "uom",
    "in_stock",
    "stock_qty",
    "show_in_home_screen",
    "is_featured",
    "sequence_id",
    "image",
    "video",
    "description",
    "pack_info",
    "tags",
    "tag",
    "delivery_mins",
]


def _appe_items(names):
    names = [group for group in names if group]
    if not names or not frappe.db.exists("DocType", "Appe Item"):
        return []
    return _rows(
        "Appe Item",
        _APPE_ITEM_FIELDS,
        filters={"status": "Active", "category": ["in", names]},
        order_by="sequence_id asc",
    )


def _items_for_groups(group_names):
    names = [group for group in group_names if group]
    if not names:
        return []
    rows = _rows(
        "Item",
        _ERP_ITEM_FIELDS,
        filters={"disabled": 0, "item_group": ["in", names]},
        order_by="item_name asc",
    )
    rates = _selling_rate_map([row.get("item_code") or row.get("name") for row in rows])
    items = []
    for row in rows:
        if (row.get("status") or "Active") != "Active":
            continue
        code = row.get("item_code") or row.get("name")
        price = rates.get(code) or row.get("standard_rate") or 0
        items.append(_map_item(row, rate=price))
    return items


@frappe.whitelist(allow_guest=True)
def get_category(name, include_items=1):
    include = str(include_items).strip().lower() not in ("0", "false", "no")
    if _erpnext_installed():
        _ensure_erpnext_fields()
        doc = _doc("Item Group", name)
        if (doc.get("status") or "Active") != "Active":
            frappe.throw(_("Category is not available"), frappe.PermissionError)
        children = _descendant_item_groups(name)
        group_names = [name] + [child.get("name") for child in children]
        items = _items_for_groups(group_names) if include else []
        return {
            "category": _map_item_group(doc.as_dict()),
            "children": children,
            "items": items,
        }
    doc = _doc("Appe Category", name)
    if (doc.get("status") or "") != "Active":
        frappe.throw(_("Category is not available"), frappe.PermissionError)
    children = _rows(
        "Appe Category",
        [
            "name",
            "category",
            "title",
            "subtitle",
            "description",
            "status",
            "sequence_id",
            "show_in_home_screen",
            "show_in_bestsellers",
            "is_group",
            "parent_appe_category",
            "icon",
            "background_image",
            "color_1",
            "color_2",
            "search_hint",
            "extra_count_label",
        ],
        filters={"status": "Active", "parent_appe_category": name},
        order_by="sequence_id asc",
    )
    item_groups = [name] + [child.get("name") for child in children if child.get("name")]
    items = []
    if include:
        items = _rows(
            "Appe Item",
            [
                "name",
                "item_code",
                "item_name",
                "subtitle",
                "brand",
                "category",
                "status",
                "mrp",
                "rate",
                "discount_percentage",
                "uom",
                "in_stock",
                "stock_qty",
                "show_in_home_screen",
                "is_featured",
                "sequence_id",
                "image",
                "video",
                "description",
                "pack_info",
                "tags",
                "tag",
                "delivery_mins",
            ],
            filters={"status": "Active", "category": ["in", item_groups]},
            order_by="sequence_id asc",
        )
    return {"category": doc.as_dict(), "children": children, "items": items}


def _category_page_bounds(limit, start, default_limit=20, max_limit=40):
    try:
        page_limit = int(limit or default_limit)
    except Exception:
        page_limit = default_limit
    if page_limit < 1:
        page_limit = default_limit
    if page_limit > max_limit:
        page_limit = max_limit
    try:
        page_start = int(start or 0)
    except Exception:
        page_start = 0
    if page_start < 0:
        page_start = 0
    return page_limit, page_start


def _category_product_order(sort):
    key = str(sort or "relevance").strip().lower()
    if key == "price_low":
        return "standard_rate asc, item_name asc"
    if key == "price_high":
        return "standard_rate desc, item_name asc"
    if key == "discount":
        return "discount_percentage desc, item_name asc"
    return "sequence_id asc, item_name asc"


@frappe.whitelist(allow_guest=True)
def get_category_products(name, limit=20, start=0, sort="relevance"):
    """One page of products for a category. The next page loads on scroll."""
    page_limit, page_start = _category_page_bounds(limit, start)
    order = _category_product_order(sort)
    if _erpnext_installed():
        _ensure_erpnext_fields()
        if not frappe.db.exists("Item Group", name):
            return {"items": [], "total": 0, "start": page_start, "limit": page_limit}
        doc = _doc("Item Group", name)
        if (doc.get("status") or "Active") != "Active":
            frappe.throw(_("Category is not available"), frappe.PermissionError)
        children = _descendant_item_groups(name)
        names = [name] + [child.get("name") for child in children if child.get("name")]
        filters = {
            "disabled": 0,
            "item_group": ["in", names],
            "status": "Active",
        }
        total = frappe.db.count("Item", filters)
        rows = _rows(
            "Item",
            _ERP_ITEM_FIELDS,
            filters=filters,
            order_by=order,
            limit=page_limit,
            start=page_start,
        )
        rates = _selling_rate_map([row.get("item_code") or row.get("name") for row in rows])
        items = []
        for row in rows:
            code = row.get("item_code") or row.get("name")
            price = rates.get(code) or row.get("standard_rate") or 0
            items.append(_map_item(row, rate=price))
        return {"items": items, "total": total, "start": page_start, "limit": page_limit}
    if not frappe.db.exists("Appe Category", name):
        return {"items": [], "total": 0, "start": page_start, "limit": page_limit}
    doc = _doc("Appe Category", name)
    if (doc.get("status") or "") != "Active":
        frappe.throw(_("Category is not available"), frappe.PermissionError)
    children = _rows(
        "Appe Category",
        ["name"],
        filters={"status": "Active", "parent_appe_category": name},
        order_by="sequence_id asc",
    )
    names = [name] + [child.get("name") for child in children if child.get("name")]
    filters = {"status": "Active", "category": ["in", names]}
    total = frappe.db.count("Appe Item", filters) if frappe.db.exists("DocType", "Appe Item") else 0
    items = _rows(
        "Appe Item",
        _APPE_ITEM_FIELDS,
        filters=filters,
        order_by=order.replace("standard_rate", "rate"),
        limit=page_limit,
        start=page_start,
    )
    return {"items": items, "total": total, "start": page_start, "limit": page_limit}


@frappe.whitelist(allow_guest=True)
def get_items():
    if _erpnext_installed():
        _ensure_erpnext_fields()
        rows = _rows(
            "Item",
            [
                "name",
                "item_code",
                "item_name",
                "item_group",
                "brand",
                "stock_uom",
                "disabled",
                "standard_rate",
                "image",
                "description",
                "subtitle",
                "status",
                "mrp",
                "discount_percentage",
                "in_stock",
                "show_in_home_screen",
                "is_featured",
                "sequence_id",
                "video",
                "pack_info",
                "tags",
                "delivery_mins",
                "has_variants",
            ],
            filters={"disabled": 0, "is_sales_item": 1, "has_variants": 0},
            order_by="sequence_id asc, item_name asc",
        )
        rates = _selling_rate_map([row.get("item_code") or row.get("name") for row in rows])
        items = []
        for row in rows:
            if (row.get("status") or "Active") != "Active":
                continue
            code = row.get("item_code") or row.get("name")
            price = rates.get(code) or row.get("standard_rate") or 0
            items.append(_map_item(row, rate=price))
        return items
    return _rows(
        "Appe Item",
        [
            "name",
            "item_code",
            "item_name",
            "subtitle",
            "brand",
            "category",
            "status",
            "mrp",
            "rate",
            "discount_percentage",
            "uom",
            "in_stock",
            "stock_qty",
            "show_in_home_screen",
            "is_featured",
            "sequence_id",
            "image",
            "video",
            "description",
            "pack_info",
            "tags",
            "tag",
            "delivery_mins",
        ],
        filters={"status": "Active"},
        order_by="sequence_id asc",
    )


def _as_int(value, default=0):
    try:
        return int(value or default)
    except Exception:
        return default


def _product_category_names():
    names = []
    if _erpnext_installed() and frappe.db.exists("DocType", "Item"):
        names = frappe.db.sql_list(
            """
            select distinct item_group
            from `tabItem`
            where disabled = 0 and ifnull(item_group, '') != ''
            """
        )
    elif frappe.db.exists("DocType", "Appe Item"):
        names = frappe.db.sql_list(
            """
            select distinct category
            from `tabAppe Item`
            where status = 'Active' and ifnull(category, '') != ''
            """
        )
    skip = {"All Item Groups", "All Item Group", "Categories"}
    return [name for name in names if name and name not in skip]


def _category_row(name):
    if _erpnext_installed():
        if frappe.db.exists("Item Group", name):
            return _map_item_group(_doc("Item Group", name).as_dict())
        return {"name": name, "title": name, "category": name, "status": "Active", "sequence_id": 0}
    if frappe.db.exists("DocType", "Appe Category") and frappe.db.exists("Appe Category", name):
        return _doc("Appe Category", name).as_dict()
    return {"name": name, "title": name, "category": name, "status": "Active", "sequence_id": 0}


def _section_items(name, limit=8):
    if _erpnext_installed():
        return _items_for_groups([name])[:limit]
    return _appe_items([name])[:limit]


def _dedupe_items(rows):
    seen = set()
    unique = []
    for row in rows:
        key = row.get("name") or row.get("item_code")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _like_rows(doctype, fields, columns, text, limit=20, filters=None):
    like = f"%{text}%"
    or_filters = [[column, "like", like] for column in columns]
    safe = _fields(doctype, fields)
    if "name" not in safe:
        safe.insert(0, "name")
    return frappe.get_all(
        doctype,
        fields=safe,
        filters=filters or {},
        or_filters=or_filters,
        limit_page_length=limit,
        ignore_permissions=True,
    )


@frappe.whitelist(allow_guest=True)
def search(query=""):
    """Search Item Groups and Items. Appe doctypes only when ERPNext is absent."""
    text = (query or "").strip()
    if len(text) < 1:
        return {"categories": [], "items": []}
    if _erpnext_installed():
        _ensure_erpnext_fields()
        categories = []
        for row in _like_rows(
            "Item Group",
            _ITEM_GROUP_FIELDS,
            ["item_group_name", "name"],
            text,
            limit=20,
        ):
            if (row.get("name") or "") in ("All Item Groups", "All Item Group", "Categories"):
                continue
            if (row.get("status") or "Active") != "Active":
                continue
            categories.append(_map_item_group(row))
        rows = _like_rows(
            "Item",
            _ERP_ITEM_FIELDS,
            ["item_name", "item_code", "name"],
            text,
            limit=30,
            filters={"disabled": 0},
        )
        rates = _selling_rate_map([row.get("item_code") or row.get("name") for row in rows])
        items = []
        for row in rows:
            if (row.get("status") or "Active") != "Active":
                continue
            code = row.get("item_code") or row.get("name")
            price = rates.get(code) or row.get("standard_rate") or 0
            items.append(_map_item(row, rate=price))
        return {"categories": categories[:20], "items": items[:30]}
    categories = []
    if frappe.db.exists("DocType", "Appe Category"):
        for row in _like_rows(
            "Appe Category",
            [
                "name",
                "category",
                "title",
                "subtitle",
                "description",
                "status",
                "sequence_id",
                "is_group",
                "parent_appe_category",
                "icon",
                "background_image",
            ],
            ["title", "category", "name"],
            text,
            limit=20,
            filters={"status": "Active"},
        ):
            categories.append(row)
    items = []
    if frappe.db.exists("DocType", "Appe Item"):
        items = _like_rows(
            "Appe Item",
            _APPE_ITEM_FIELDS,
            ["item_name", "item_code", "name"],
            text,
            limit=30,
            filters={"status": "Active"},
        )
    return {"categories": categories, "items": items}


@frappe.whitelist(allow_guest=True)
def get_popular_items():
    """Featured and home-screen items. Separate from the full catalog."""
    if _erpnext_installed():
        _ensure_erpnext_fields()
        rows = []
        rows.extend(
            _rows("Item", _ERP_ITEM_FIELDS, filters={"disabled": 0, "is_featured": 1}, limit=12)
        )
        rows.extend(
            _rows(
                "Item",
                _ERP_ITEM_FIELDS,
                filters={"disabled": 0, "show_in_home_screen": 1},
                limit=12,
            )
        )
        rows = _dedupe_items(rows)
        if rows:
            rates = _selling_rate_map([row.get("item_code") or row.get("name") for row in rows])
            items = []
            for row in rows:
                if (row.get("status") or "Active") != "Active":
                    continue
                code = row.get("item_code") or row.get("name")
                price = rates.get(code) or row.get("standard_rate") or 0
                items.append(_map_item(row, rate=price))
            return items[:12]
        return []
    if not frappe.db.exists("DocType", "Appe Item"):
        return []
    rows = []
    rows.extend(
        _rows("Appe Item", _APPE_ITEM_FIELDS, filters={"status": "Active", "is_featured": 1}, limit=12)
    )
    rows.extend(
        _rows(
            "Appe Item",
            _APPE_ITEM_FIELDS,
            filters={"status": "Active", "show_in_home_screen": 1},
            limit=12,
        )
    )
    return _dedupe_items(rows)[:12]


@frappe.whitelist(allow_guest=True)
def get_home_sections(start=0, limit=3):
    """Next page of category rails. Only categories that have products."""
    if _erpnext_installed():
        _ensure_erpnext_fields()
    start = max(_as_int(start), 0)
    limit = _as_int(limit, 3) or 3
    names = _product_category_names()
    ordered = []
    for name in names:
        row = _category_row(name)
        ordered.append((_as_int(row.get("sequence_id")), name, row))
    ordered.sort(key=lambda row: (row[0], row[1]))
    page = ordered[start : start + limit]
    sections = []
    for _, name, row in page:
        items = _section_items(name, 8)
        if not items:
            continue
        sections.append({"category": row, "items": items})
    return {"start": start, "total": len(ordered), "sections": sections}


@frappe.whitelist(allow_guest=True)
def get_item(name):
    if _erpnext_installed():
        _ensure_erpnext_fields()
        doc = _doc("Item", name)
        if int(doc.get("disabled") or 0) or (doc.get("status") or "Active") != "Active":
            frappe.throw(_("Item is not available"), frappe.PermissionError)
        data = doc.as_dict()
        code = data.get("item_code") or data.get("name")
        price = _selling_rate_map([code]).get(code) or data.get("standard_rate") or 0
        return _map_item(data, rate=price, detail=data)
    doc = _doc("Appe Item", name)
    if (doc.get("status") or "") != "Active":
        frappe.throw(_("Item is not available"), frappe.PermissionError)
    return doc.as_dict()


def _file_urls(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        urls = []
        for row in raw:
            if isinstance(row, dict):
                url = row.get("file_url") or row.get("image") or row.get("banner") or ""
            else:
                url = str(row)
            url = (url or "").strip()
            if url:
                urls.append(url)
        return urls
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            return _file_urls(json.loads(text))
        except Exception:
            return [text]
    return [part.strip() for part in text.split(",") if part.strip()]


@frappe.whitelist(allow_guest=True)
def get_banners():
    """Home banner slider. Uses Appe Banner when that DocType exists."""
    if frappe.db.exists("DocType", "Appe Banner"):
        return _rows(
            "Appe Banner",
            [
                "name",
                "title",
                "subtitle",
                "image",
                "category",
                "status",
                "sequence_id",
                "color",
            ],
            filters={"status": "Active"},
            order_by="sequence_id asc",
            limit=12,
        )

    banners = []
    if _erpnext_installed():
        categories = get_categories()
    else:
        categories = _rows(
        "Appe Category",
        [
            "name",
            "title",
            "category",
            "subtitle",
            "banner",
            "background_image",
            "status",
            "sequence_id",
        ],
        filters={"status": "Active"},
        order_by="sequence_id asc",
    )
    for cat in categories:
        title = (cat.get("title") or cat.get("category") or cat.get("name") or "").strip()
        subtitle = (cat.get("subtitle") or "").strip()
        urls = _file_urls(cat.get("banner"))
        if not urls and cat.get("background_image"):
            urls = _file_urls(cat.get("background_image"))
        for url in urls:
            banners.append(
                {
                    "name": f"{cat.get('name')}-{len(banners) + 1}",
                    "title": title,
                    "subtitle": subtitle,
                    "image": url,
                    "category": cat.get("name"),
                    "status": "Active",
                    "sequence_id": cat.get("sequence_id") or 0,
                }
            )
            if len(banners) >= 12:
                return banners
    return banners


def _ensure_home_popup_doctype():
    if getattr(frappe.local, "appe_home_popup_ready", False):
        return
    if not frappe.db.exists("DocType", "Appe Home Popup"):
        frappe.get_doc(
            {
                "doctype": "DocType",
                "name": "Appe Home Popup",
                "module": "Custom",
                "custom": 1,
                "autoname": "hash",
                "title_field": "title",
                "sort_field": "sequence_id",
                "sort_order": "ASC",
                "fields": [
                    {
                        "fieldname": "title",
                        "label": "Text",
                        "fieldtype": "Small Text",
                        "in_list_view": 1,
                    },
                    {
                        "fieldname": "button_text",
                        "label": "Button Text",
                        "fieldtype": "Data",
                        "in_list_view": 1,
                    },
                    {
                        "fieldname": "color",
                        "label": "Button Color",
                        "fieldtype": "Color",
                    },
                    {
                        "fieldname": "button_text_color",
                        "label": "Button Text Color",
                        "fieldtype": "Color",
                    },
                    {
                        "fieldname": "text_color",
                        "label": "Text Color",
                        "fieldtype": "Color",
                    },
                    {
                        "fieldname": "action",
                        "label": "Action",
                        "fieldtype": "Select",
                        "options": "\nNone\nProfile\nCategory\nProduct\nCart\nSearch\nOrders\nWallet\nFavorites\nURL",
                        "default": "None",
                    },
                    {
                        "fieldname": "action_value",
                        "label": "Action Value",
                        "fieldtype": "Data",
                        "description": "Category, product, or URL for the action",
                    },
                    {
                        "fieldname": "icon",
                        "label": "Icon",
                        "fieldtype": "Data",
                        "description": "assignment, store, cart, offer, gift, info, percent, restaurant, bell, wallet",
                    },
                    {
                        "fieldname": "image",
                        "label": "Image",
                        "fieldtype": "Attach Image",
                    },
                    {
                        "fieldname": "big_image",
                        "label": "Big Image",
                        "fieldtype": "Attach Image",
                    },
                    {
                        "fieldname": "status",
                        "label": "Status",
                        "fieldtype": "Select",
                        "options": "Active\nInactive",
                        "default": "Active",
                        "in_list_view": 1,
                    },
                    {
                        "fieldname": "sequence_id",
                        "label": "Sequence",
                        "fieldtype": "Int",
                        "default": "0",
                    },
                ],
                "permissions": [
                    {
                        "role": "System Manager",
                        "read": 1,
                        "write": 1,
                        "create": 1,
                        "delete": 1,
                    }
                ],
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
    frappe.local.appe_home_popup_ready = True


@frappe.whitelist(allow_guest=True)
def get_home_popup():
    """Bottom home popup. Empty when no active Appe Home Popup exists."""
    _ensure_home_popup_doctype()
    rows = _rows(
        "Appe Home Popup",
        [
            "name",
            "title",
            "button_text",
            "color",
            "button_text_color",
            "text_color",
            "action",
            "action_value",
            "icon",
            "image",
            "big_image",
            "status",
            "sequence_id",
        ],
        filters={"status": "Active"},
        order_by="sequence_id asc",
        limit=1,
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "name": row.get("name") or "",
        "title": row.get("title") or "",
        "button_text": row.get("button_text") or "",
        "color": row.get("color") or "",
        "button_text_color": row.get("button_text_color") or "",
        "text_color": row.get("text_color") or "",
        "action": row.get("action") or "",
        "action_value": row.get("action_value") or "",
        "icon": row.get("icon") or "",
        "image": row.get("image") or "",
        "big_image": row.get("big_image") or "",
    }


@frappe.whitelist(allow_guest=True)
def get_offers():
    return _rows(
        "Appe Offer",
        [
            "name",
            "title",
            "subtitle",
            "status",
            "sequence_id",
            "category",
            "color",
            "icon",
            "image",
            "url",
            "show_in_home_screen",
        ],
        filters={"status": "Active"},
        order_by="sequence_id asc",
    )


@frappe.whitelist()
def get_orders():
    user = _user()
    if _erpnext_installed():
        _ensure_erpnext_fields()
        customer = _customer_for(user)
        names = frappe.get_all(
            "Quotation",
            filters={"quotation_to": "Customer", "party_name": customer.name},
            pluck="name",
            order_by="modified desc",
            limit_page_length=100,
            ignore_permissions=True,
        )
        return [_map_sales_order(_doc("Quotation", name)) for name in names]
    return _rows(
        "Appe Order",
        [
            "name",
            "user",
            "customer_name",
            "status",
            "delivery_address",
            "total_qty",
            "grand_total",
            "notes",
            "cancel_reason",
            "creation",
            "modified",
        ],
        filters={"user": user},
        order_by="modified desc",
        limit=100,
    )


@frappe.whitelist()
def get_order(name):
    user = _user()
    if _erpnext_installed():
        _ensure_erpnext_fields()
        customer = _customer_for(user)
        doc = _doc("Quotation", name)
        if doc.get("party_name") != customer.name and "System Manager" not in frappe.get_roles(user):
            frappe.throw(_("Not permitted"), frappe.PermissionError)
        return _map_sales_order(doc, with_items=True)
    doc = _doc("Appe Order", name)
    if doc.get("user") != user and "System Manager" not in frappe.get_roles(user):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    return doc.as_dict()


@frappe.whitelist()
def place_order(delivery_address="", notes="", items=None, customer_name=""):
    user = _user()
    if isinstance(items, str):
        items = json.loads(items or "[]")
    items = items or []
    if not items:
        frappe.throw(_("Cart is empty"))

    if _erpnext_installed():
        _ensure_erpnext_fields()
        customer = _customer_for(user)
        if customer_name and customer_name != customer.customer_name:
            customer.customer_name = customer_name
            customer.flags.ignore_permissions = True
            customer.save(ignore_permissions=True)
        company = _company()
        currency = frappe.db.get_value("Company", company, "default_currency") or "INR"
        price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
        if not price_list:
            price_list = frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name")
        quote_items = []
        for raw in items:
            qty = float(raw.get("qty") or 0)
            if qty <= 0:
                continue
            item_code = raw.get("item") or raw.get("item_code")
            if not item_code:
                continue
            row = {"item_code": item_code, "qty": qty, "rate": float(raw.get("rate") or 0)}
            uom = frappe.db.get_value("Item", item_code, "stock_uom")
            if uom:
                row["uom"] = uom
            quote_items.append(row)
        if not quote_items:
            frappe.throw(_("Cart is empty"))
        note_text = (notes or "").strip()
        if delivery_address:
            note_text = delivery_address if not note_text else f"{delivery_address}\n{note_text}"
        doc = frappe.get_doc(
            {
                "doctype": "Quotation",
                "quotation_to": "Customer",
                "party_name": customer.name,
                "customer_name": customer.customer_name,
                "company": company,
                "transaction_date": frappe.utils.today(),
                "valid_till": frappe.utils.add_days(frappe.utils.today(), 30),
                "order_type": "Sales",
                "currency": currency,
                "selling_price_list": price_list,
                "items": quote_items,
                "terms": note_text,
            }
        )
        doc.flags.ignore_permissions = True
        doc.set_missing_values()
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return _map_sales_order(doc, with_items=True)

    total_qty = 0
    grand_total = 0
    rows = []
    for raw in items:
        qty = float(raw.get("qty") or 0)
        rate = float(raw.get("rate") or 0)
        amount = qty * rate
        total_qty += qty
        grand_total += amount
        rows.append(
            {
                "item": raw.get("item"),
                "item_name": raw.get("item_name"),
                "uom": raw.get("uom"),
                "qty": qty,
                "rate": rate,
                "amount": amount,
            }
        )

    doc = frappe.get_doc(
        {
            "doctype": "Appe Order",
            "user": user,
            "customer_name": customer_name or frappe.db.get_value("User", user, "full_name") or user,
            "status": "Placed",
            "delivery_address": delivery_address or "Delivering to Work",
            "notes": notes or "",
            "items": rows,
            "total_qty": total_qty,
            "grand_total": grand_total,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def cancel_order(name, reason):
    user = _user()
    reason = (reason or "").strip()
    if not reason:
        frappe.throw(_("Please enter cancel reason"))
    if _erpnext_installed():
        _ensure_erpnext_fields()
        customer = _customer_for(user)
        doc = _doc("Quotation", name)
        if doc.get("party_name") != customer.name and "System Manager" not in frappe.get_roles(user):
            frappe.throw(_("Not permitted"), frappe.PermissionError)
        if int(doc.docstatus or 0) == 2 or (doc.get("status") or "") in ("Cancelled", "Lost", "Expired"):
            return {
                "success": True,
                "message": f"Quotation {name} is already cancelled",
                "order": _map_sales_order(doc, with_items=True),
            }
        if (doc.get("status") or "") in ("Ordered", "Partially Ordered"):
            frappe.throw(_("This quotation is already ordered and cannot be cancelled"))
        if doc.meta.has_field("cancel_reason"):
            doc.cancel_reason = reason
        doc.flags.ignore_permissions = True
        if int(doc.docstatus or 0) == 0:
            doc.save(ignore_permissions=True)
            doc.submit()
        doc.cancel()
        frappe.db.commit()
        doc.reload()
        return {
            "success": True,
            "message": f"Quotation {name} cancelled successfully",
            "order": _map_sales_order(doc, with_items=True),
        }
    doc = _doc("Appe Order", name)
    if doc.get("user") != user and "System Manager" not in frappe.get_roles(user):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    status = (doc.get("status") or "").lower()
    if status == "cancelled":
        return {"success": True, "message": f"Order {name} is already cancelled", "order": doc.as_dict()}
    if status == "delivered":
        frappe.throw(_("Delivered order cannot be cancelled"))
    note_line = f"Cancel reason: {reason}"
    notes = (doc.get("notes") or "").strip()
    doc.status = "Cancelled"
    if doc.meta.has_field("cancel_reason"):
        doc.cancel_reason = reason
    doc.notes = note_line if not notes else f"{notes}\n{note_line}"
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True, "message": f"Order {name} cancelled successfully", "order": doc.as_dict()}


@frappe.whitelist()
def get_favorites():
    user = _user()
    rows = _rows(
        "Appe Favorite",
        ["name", "item", "user"],
        filters={"user": user},
        order_by="modified desc",
    )
    return [row.get("item") for row in rows if row.get("item")]


@frappe.whitelist()
def add_favorite(item):
    user = _user()
    item = (item or "").strip()
    if not item:
        frappe.throw(_("Item is required"))
    existing = frappe.db.exists("Appe Favorite", {"user": user, "item": item})
    if existing:
        return {"ok": True, "name": existing}
    doc = frappe.get_doc({"doctype": "Appe Favorite", "user": user, "item": item})
    doc.flags.ignore_permissions = True
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True, ignore_links=True)
    frappe.db.commit()
    return {"ok": True, "name": doc.name}


@frappe.whitelist()
def remove_favorite(item):
    user = _user()
    item = (item or "").strip()
    names = frappe.get_all(
        "Appe Favorite",
        filters={"user": user, "item": item},
        pluck="name",
        ignore_permissions=True,
    )
    for name in names:
        frappe.delete_doc("Appe Favorite", name, ignore_permissions=True, force=True)
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def get_recent_views():
    user = _user()
    if not frappe.db.exists("DocType", "Appe Recent View"):
        return []
    return _rows(
        "Appe Recent View",
        ["name", "user", "item", "item_name", "image", "rate", "category", "modified"],
        filters={"user": user},
        order_by="modified desc",
        limit=12,
    )


@frappe.whitelist()
def add_recent_view(item, item_name="", image="", rate=0, category=""):
    user = _user()
    if not frappe.db.exists("DocType", "Appe Recent View"):
        frappe.throw(_("Create the Appe Recent View DocType first"))
    item = (item or "").strip()
    if not item:
        frappe.throw(_("Item is required"))
    existing = frappe.get_all(
        "Appe Recent View",
        filters={"user": user, "item": item},
        pluck="name",
        ignore_permissions=True,
    )
    for name in existing:
        frappe.delete_doc("Appe Recent View", name, ignore_permissions=True, force=True)
    doc = frappe.get_doc(
        {
            "doctype": "Appe Recent View",
            "user": user,
            "item": item,
            "item_name": item_name or item,
            "image": image or "",
            "rate": rate or 0,
            "category": category or "",
        }
    )
    doc.flags.ignore_permissions = True
    doc.flags.ignore_links = True
    doc.insert(ignore_permissions=True, ignore_links=True)
    extra = frappe.get_all(
        "Appe Recent View",
        filters={"user": user},
        pluck="name",
        order_by="modified desc",
        limit_start=12,
        limit_page_length=100,
        ignore_permissions=True,
    )
    for name in extra:
        frappe.delete_doc("Appe Recent View", name, ignore_permissions=True, force=True)
    frappe.db.commit()
    return {"ok": True, "name": doc.name}


def _wallet_for(user):
    name = frappe.db.get_value("Appe Wallet", {"user": user}, "name")
    if name:
        return _doc("Appe Wallet", name)
    doc = frappe.get_doc({"doctype": "Appe Wallet", "user": user, "balance": 0})
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc


@frappe.whitelist()
def get_wallet():
    user = _user()
    if not frappe.db.exists("DocType", "Appe Wallet"):
        return {"name": "", "user": user, "balance": 0, "entries": []}
    return _wallet_for(user).as_dict()


def _profile_for(user):
    name = frappe.db.get_value("Appe Customer Profile", {"user": user}, "name")
    if name:
        return _doc("Appe Customer Profile", name)
    full_name = frappe.db.get_value("User", user, "full_name") or user
    doc = frappe.get_doc(
        {
            "doctype": "Appe Customer Profile",
            "user": user,
            "full_name": full_name,
            "email": user,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc


@frappe.whitelist()
def get_addresses():
    user = _user()
    if not _erpnext_installed():
        return []
    _ensure_erpnext_fields()
    customer = _customer_for(user)
    return _customer_addresses(customer.name)


@frappe.whitelist()
def save_address(address_line1="", city="", state="", pincode="", address_line2="", phone="", gstin="", title="", address_type="Shipping"):
    user = _user()
    if not _erpnext_installed():
        frappe.throw(_("Addresses are stored on the customer in ERPNext"))
    _ensure_erpnext_fields()
    line = (address_line1 or "").strip()
    place = (city or "").strip()
    if not line or not place:
        frappe.throw(_("Enter the address and city"))
    customer = _customer_for(user)
    clean_state = _clean_state(state)
    clean_gstin = _clean_gstin(gstin)
    if clean_gstin:
        _apply_customer_gstin(customer, clean_gstin)
        customer.flags.ignore_permissions = True
        customer.save(ignore_permissions=True)
    doc = _insert_customer_address(
        customer,
        address_line1=line,
        city=place,
        state=clean_state,
        pincode=(pincode or "").strip(),
        address_line2=(address_line2 or "").strip(),
        phone=(phone or "").strip(),
        email=user if "@" in (user or "") else "",
        gstin=clean_gstin,
        address_type=_clean_address_type(address_type),
        title=(title or "").strip(),
    )
    frappe.db.commit()
    return _map_address(doc)


@frappe.whitelist(allow_guest=True)
def signup(email="", first_name="", last_name="", company="", phone="", gstin="", state=""):
    email = (email or "").strip().lower()
    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()
    company = (company or "").strip()
    phone = (phone or "").strip()
    if not first_name:
        frappe.throw(_("Enter your first name"))
    if not company:
        frappe.throw(_("Enter the company name"))
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        frappe.throw(_("Enter a valid email"))
    if len(re.sub(r"\D", "", phone)) < 10:
        frappe.throw(_("Enter a valid mobile number"))
   
    if frappe.db.exists("User", email):
        frappe.throw(_("An account with this email already exists. Please login."))
    clean_state = _clean_state(state) if (state or "").strip() else ""
    clean_gstin = _clean_gstin(gstin)

    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "mobile_no": phone,
            "enabled": 1,
            "user_type": "Website User",
            "send_welcome_email": 0,
        }
    )
    user.flags.ignore_permissions = True
    user.insert(ignore_permissions=True)
    if frappe.db.exists("Role", "Customer"):
        try:
            user.add_roles("Customer")
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Signup customer role")

    customer_name = ""
    if _erpnext_installed():
        _ensure_erpnext_fields()
        customer_name = company or " ".join(part for part in [first_name, last_name] if part)
        if frappe.db.exists("Customer", customer_name):
            customer_name = f"{customer_name} - {email}"
        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": customer_name,
                "customer_type": "Company",
                "customer_group": _leaf("Customer Group"),
                "territory": _leaf("Territory"),
                "email_id": email,
                "mobile_no": phone,
                "portal_users": [{"user": email}],
            }
        )
        _apply_customer_gstin(customer, clean_gstin)
        customer.flags.ignore_permissions = True
        customer.insert(ignore_permissions=True)
        _insert_customer_address(
            customer,
            address_line1=company or customer.customer_name,
            city=clean_state or company,
            state=clean_state,
            phone=phone,
            email=email,
            gstin=clean_gstin,
            address_type="Billing",
            title=customer.customer_name,
        )

    frappe.db.commit()
    return {"ok": True, "email": email, "customer": customer_name}


@frappe.whitelist()
def get_profile():
    user = _user()
    if _erpnext_installed():
        return _profile_payload(user, _customer_for(user))
    if not frappe.db.exists("DocType", "Appe Customer Profile"):
        full_name = frappe.db.get_value("User", user, "full_name") or user
        return {"name": "", "user": user, "full_name": full_name, "email": user}
    return _profile_for(user).as_dict()


@frappe.whitelist()
def save_profile(full_name="", phone="", email="", address="", city="", pincode=""):
    user = _user()
    if _erpnext_installed():
        customer = _customer_for(user)
        if full_name:
            customer.customer_name = full_name
        if customer.meta.has_field("mobile_no"):
            customer.mobile_no = phone or ""
        if customer.meta.has_field("email_id"):
            customer.email_id = email or (user if "@" in user else customer.get("email_id"))
        customer.flags.ignore_permissions = True
        customer.save(ignore_permissions=True)
        addr = _customer_address(customer.name)
        country = frappe.db.get_default("country") or frappe.db.get_value("Country", {}, "name") or "India"
        if addr:
            addr.address_line1 = address or addr.get("address_line1") or "-"
            addr.city = city or addr.get("city") or "-"
            addr.pincode = pincode or addr.get("pincode") or ""
            addr.flags.ignore_permissions = True
            addr.save(ignore_permissions=True)
        elif address or city or pincode:
            addr = frappe.get_doc(
                {
                    "doctype": "Address",
                    "address_title": customer.customer_name,
                    "address_type": "Shipping",
                    "address_line1": address or "-",
                    "city": city or "-",
                    "pincode": pincode or "",
                    "country": country,
                    "links": [{"link_doctype": "Customer", "link_name": customer.name}],
                }
            )
            addr.flags.ignore_permissions = True
            addr.insert(ignore_permissions=True)
        frappe.db.commit()
        return _profile_payload(user, customer)
    doc = _profile_for(user)
    doc.full_name = full_name or doc.get("full_name")
    doc.phone = phone or ""
    doc.email = email or user
    doc.address = address or ""
    doc.city = city or ""
    doc.pincode = pincode or ""
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.as_dict()


@frappe.whitelist()
def download_order_pdf(name):
    get_order(name)
    doctype = "Quotation" if _erpnext_installed() else "Appe Order"
    html = frappe.get_print(doctype, name)
    from frappe.utils.pdf import get_pdf

    frappe.local.response.filename = f"{name}.pdf"
    frappe.local.response.filecontent = get_pdf(html)
    frappe.local.response.type = "pdf"
