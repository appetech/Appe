# import base64
# import frappe
# import numpy as np
# import face_recognition
# from io import BytesIO
# import pickle
# from frappe.utils.file_manager import save_file
# import cv2

# def load_all_face_encodings():
#     records = frappe.get_all("Employee Face", fields=["employee_id", "face_encoding"])
#     known_encodings, known_employee_ids = [], []
#     for rec in records:
#         if not rec.face_encoding: continue
#         try:
#             encoding_array = pickle.loads(base64.b64decode(rec.face_encoding))
#             known_encodings.append(encoding_array)
#             known_employee_ids.append(rec.employee_id)
#         except Exception as e: frappe.logger().error(f"[Encoding Load Error] {rec.employee_id}: {e}")
#     return np.array(known_encodings), known_employee_ids


# def check_liveness(opencv_image):

#     try:
#         face_locations = face_recognition.face_locations(opencv_image)
#         if not face_locations:
#             return {"status": False, "score": 0, "message": "No face detected for liveness check."}
        
#         top, right, bottom, left = face_locations[0]
#         face_crop = opencv_image[top:bottom, left:right]
        
#         LIVENESS_THRESHOLD = 0.85
        
#         if liveness_probability_real >= LIVENESS_THRESHOLD:
#             return {"status": True, "score": liveness_probability_real}
#         else:
#             return {"status": False, "score": liveness_probability_real}
            
#     except Exception as e:
#         frappe.log_error(f"Liveness Check Failed: {e}")
#         return {"status": False, "score": 0, "message": f"Error: {e}"}



# @frappe.whitelist()
# def identify_employee(image_url=None, data=None, tolerance=0.55):
#     if not image_url and not data:
#         return {"status": False, "message": "No image data or URL provided."}

#     known_encodings, known_employee_ids = load_all_face_encodings()
#     if len(known_encodings) == 0:
#         return {"status": False, "message": "No enrolled faces found."}

#     try:
#         if data and (data.startswith("data:image") or len(data) > 500):
#             if "," in data: data = data.split(",")[1]
#             image_bytes = base64.b64decode(data)
#             nparr = np.frombuffer(image_bytes, np.uint8)
#             opencv_image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
#             unknown_image_rgb = cv2.cvtColor(opencv_image_bgr, cv2.COLOR_BGR2RGB)
#         else:
#             target_url = image_url or data
#             import requests
#             response = requests.get(target_url if not target_url.startswith("/") else frappe.utils.get_url()+target_url)
#             unknown_image_rgb = face_recognition.load_image_file(BytesIO(response.content))
#             opencv_image_bgr = cv2.cvtColor(unknown_image_rgb, cv2.COLOR_RGB2BGR)

#         liveness_result = check_liveness(opencv_image_bgr)
        
#         frappe.logger().info(f"[Liveness Check] Score: {liveness_result.get('score')}, Result: {liveness_result['status']}")

#         if not liveness_result["status"]:
#             return {
#                 "status": False,
#                 "message": f"Spoofing detected (Real Score: {round(liveness_result.get('score', 0)*100)}%). Attendance rejected.",
#                 "employee": None,
#                 "is_spoof": True
#             }

#         unknown_encodings = face_recognition.face_encodings(unknown_image_rgb)

#         if len(unknown_encodings) != 1:
#             return {"status": False, "message": "Expected 1 face, please clarify image."}

#         face_distances = face_recognition.face_distance(known_encodings, unknown_encodings[0])
#         best_match_index = np.argmin(face_distances)
#         best_distance = face_distances[best_match_index]

#         if best_distance <= float(tolerance):
#             matched_employee = known_employee_ids[best_match_index]
#             frappe.logger().info(f"[Face Match Success] {matched_employee} distance: {round(best_distance, 4)}")
            
#             return {
#                 "status": True,
#                 "message": f"Identified as employee {matched_employee}",
#                 "employee": matched_employee,
#                 "user": matched_employee,
#                 "liveness_score": round(liveness_result['score'], 4)
#             }

#         return {"status": False, "message": "No matching employee found.", "employee": None}

#     except Exception as e:
#         frappe.log_error(f"Advanced recognition crash: {e}")
#         return {"status": False, "message": f"Recognition failed: {str(e)}"}

# @frappe.whitelist()
# def upload_employee_image(employee_id, image_base64):
#     try:
#         if "," in image_base64:
#             image_base64 = image_base64.split(",")[1]
            
#         file_bytes = base64.b64decode(image_base64)
#         filename = f"face_{employee_id}_{frappe.generate_hash(length=5)}.jpg"
        
#         file_doc = save_file(
#             fname=filename,
#             content=file_bytes,
#             dt="Employee Face",
#             dn=employee_id,
#             is_private=1
#         )
        
#         return {"status": True, "file_url": file_doc.file_url}
#     except Exception as e:
#         frappe.log_error("Face Image Upload Error", str(e))
#         return {"status": False, "message": str(e)}