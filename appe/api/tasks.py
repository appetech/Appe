import frappe
import json
from math import radians, sin, cos, sqrt, atan2


def haversine(lat1, lon1, lat2, lon2):
    R = 6371

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def create_daily_route_summary():

    date = frappe.utils.add_days(frappe.utils.today(), -1)

    employees = frappe.get_all(
        "Employee Location",
        fields=["employee"],
        filters={"posting_date": date},
        group_by="employee"
    )

    for emp in employees:

        process_employee(emp.employee, date)


def process_employee(employee, date):

    locations = frappe.get_all(
        "Employee Location",
        filters={
            "employee": employee
        },
        fields=[
            "latitude",
            "longitude",
            "timestamp"
        ],
        order_by="timestamp asc"
    )

    if not locations:
        return

    total_distance = 0

    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    coordinates = []

    prev = None

    for row in locations:

        if not row.latitude or not row.longitude:
            continue

        lat = float(row.latitude)
        lng = float(row.longitude)

        coordinates.append([lng, lat])

        if prev:
            total_distance += haversine(
                prev["lat"],
                prev["lng"],
                lat,
                lng
            )

        prev = {
            "lat": lat,
            "lng": lng
        }

    geojson["features"].append({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        }
    })

    activities = frappe.get_all(
        "Appe User Activity",
        filters={
            "posting_date": date,
            "owner": frappe.db.get_value(
                "Employee",
                employee,
                "user_id"
            )
        },
        fields=[
            "name",
            "subject",
            "latitude",
            "longitude",
            "creation",
            "reference_doctype",
            "reference_docname"
        ]
    )

    timeline = []

    for act in activities:

        timeline.append({
            "type": "activity",
            "time": str(act.creation),
            "title": act.subject,
            "doctype": act.reference_doctype,
            "docname": act.reference_docname,
            "lat": act.latitude,
            "lng": act.longitude
        })

    summary_name = frappe.db.exists(
        "Employee Route Summary",
        {
            "employee": employee,
            "summary_date": date
        }
    )

    if summary_name:
        doc = frappe.get_doc(
            "Employee Route Summary",
            summary_name
        )
    else:
        doc = frappe.new_doc(
            "Employee Route Summary"
        )

    doc.employee = employee
    doc.summary_date = date

    doc.start_time = locations[0].timestamp
    doc.end_time = locations[-1].timestamp

    doc.total_distance_km = round(total_distance, 2)
    doc.total_points = len(locations)
    doc.total_activities = len(activities)

    doc.route_geojson = json.dumps(geojson)
    doc.timeline_json = json.dumps(timeline)

    doc.save(ignore_permissions=True)

    frappe.db.commit()