# Copyright (c) 2025, Kamesh and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
import requests


class AppeReport(Document):
	pass
	
@frappe.whitelist()
def get_third_party_reports(appe_api_integration, text=None):
	if appe_api_integration:

		url = frappe.db.get_value("Appe API Integration",appe_api_integration,"url")
		url =url+'/api/resource/Report?fields=[\"name\"]'

		headers = {
			"Authorization": frappe.db.get_value("Appe API Integration",appe_api_integration,"token"),
			"Content-Type": "application/json"
		}
		params = {
			"fields": '["name"]',
			"filters": json.dumps([["name", "like", f"%{text}%"]]) if text else json.dumps([]),
			"limit_page_length": 20
		}
		frappe.log_error("token",params)

		response = requests.get(url, headers=headers, params=params)
		frappe.log_error("Third Party Response", response.text)


		if response.status_code != 200:
			frappe.throw(f"API Error: {response.status_code} {response.text}")

		try:
			data = response.json().get("data", [])
		except Exception:
			frappe.throw(f"Invalid JSON Response: {response.text}")

		return [d["name"] for d in data]

	else:
		return []