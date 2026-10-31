import frappe

DEFAULT_UOMS = [
	{"uom_name": "Nos", "must_be_whole_number": 1},
	{"uom_name": "Kg", "must_be_whole_number": 0},
	{"uom_name": "Gram", "must_be_whole_number": 0},
	{"uom_name": "Litre", "must_be_whole_number": 0},
	{"uom_name": "Box", "must_be_whole_number": 1},
	{"uom_name": "Packet", "must_be_whole_number": 1},
]


def create_default_appe_uoms():
	if not frappe.db.exists("DocType", "Appe UOM"):
		return {"created": 0, "skipped": 0}

	created = 0
	skipped = 0
	for uom in DEFAULT_UOMS:
		if frappe.db.exists("Appe UOM", uom["uom_name"]):
			skipped += 1
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Appe UOM",
				"uom_name": uom["uom_name"],
				"must_be_whole_number": uom["must_be_whole_number"],
				"enabled": 1,
			}
		)
		doc.insert(ignore_permissions=True)
		created += 1

	return {"created": created, "skipped": skipped, "total": len(DEFAULT_UOMS)}
