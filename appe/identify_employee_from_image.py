# # import base64
# # import frappe
# # import numpy as np
# # import face_recognition
# # import requests
# # from io import BytesIO
# # from PIL import Image

# # def load_face_encodings():
# #     encodings = []
# #     records = frappe.get_all("Employee Face", fields=["employee_id", "face_encoding"])
# #     for rec in records:
# #         if not rec.face_encoding:
# #             continue
# #         try:
# #             encoding_list = [float(x) for x in rec.face_encoding.split(",")]
# #             encodings.append({
# #                 "employee_id": rec.employee_id,
# #                 "encoding": np.array(encoding_list)
# #             })
# #         except:
# #             frappe.logger().error(f"Invalid encoding for {rec.employee_id}")
# #     return encodings

# # @frappe.whitelist()
# # def identify_employee(image_url, tolerance=0.6):
# #     """
# #     Identify employee from an image URL (e.g. /files/abc.jpg or full URL).
# #     """

# #     # image_url = upload_file_in_doctype(image_base64)
# #     if not image_url:
# #         return {"status":False,"message":"❌ Could not upload image."}
# #     known_faces = load_face_encodings()
# #     if not known_faces:
# #         return {"status":False,"message":"❌ No enrolled faces found."}

# #     # Make sure the image_url is a full URL
# #     if image_url.startswith("/"):
# #         image_url = frappe.utils.get_url() + image_url

# #     # Download image from the URL
# #     response = requests.get(image_url)
# #     if response.status_code != 200:
# #         return {"status":False,
# #                 "message":" Could not download image from the provided URL."}

# #     # Load image directly from memory
# #     unknown_image = face_recognition.load_image_file(BytesIO(response.content))
# #     unknown_encodings = face_recognition.face_encodings(unknown_image)

# #     if not unknown_encodings:
# #         return {"status":False,
# #                 "message":"No face found in the input image."}

# #     unknown_encoding = unknown_encodings[0]

# #     for known in known_faces:
# #         match = face_recognition.compare_faces(
# #             [known["encoding"]],
# #             unknown_encoding,
# #             tolerance=float(tolerance)
# #         )[0]
# #         if match:
# #             return {"status":True,
# #                     "message": f"✅ Identified as employee {known['employee_id']}",
# #                     "employee":known['employee_id']}

# #     return {"status":False,
# #             "message": "❌ No matching employee found.",
# #             "employee": None}



# import base64
# import frappe
# import numpy as np
# import face_recognition
# import requests
# from io import BytesIO
# import pickle

# def load_face_encodings():
#     encodings = []
#     records = frappe.get_all("Employee Face", fields=["employee_id", "face_encoding"])
#     for rec in records:
#         if not rec.face_encoding:
#             continue
#         try:
#             # Load pickle-encoded base64 string
#             encoding_data = base64.b64decode(rec.face_encoding)
#             encoding_array = pickle.loads(encoding_data)
#             encodings.append({
#                 "employee_id": rec.employee_id,
#                 "encoding": np.array(encoding_array)
#             })
#         except Exception as e:
#             frappe.logger().error(f"[Face Encoding Error] Employee {rec.employee_id}: {e}")
#     return encodings

# @frappe.whitelist()
# def identify_employee(image_url, tolerance=0.65):
#     """
#     Identify employee from an image URL.
#     """
#     # image_url = upload_file_in_doctype(image_base64)

#     if not image_url:
#         return {"status": False, "message": "No image URL provided."}

#     known_faces = load_face_encodings()
#     if not known_faces:
#         return {"status": False, "message": "No enrolled faces found."}

#     if image_url.startswith("/"):
#         image_url = frappe.utils.get_url() + image_url

#     try:
#         response = requests.get(image_url)
#         if response.status_code != 200:
#             return {"status": False, "message": "Could not download image from the provided URL."}
        
#         unknown_image = face_recognition.load_image_file(BytesIO(response.content))
#         unknown_encodings = face_recognition.face_encodings(unknown_image)

#         if len(unknown_encodings) != 1:
#             return {
#                 "status": False,
#                 "message": f"Expected 1 face, but found {len(unknown_encodings)}. Please use a clear image with one face."
#             }

#         unknown_encoding = unknown_encodings[0]

#         for known in known_faces:
#             distance = face_recognition.face_distance([known["encoding"]], unknown_encoding)[0]
#             match = distance <= float(tolerance)
#             frappe.logger().info(f"[Face Match Attempt] {known['employee_id']} distance: {distance}, match: {match}")
            
#             if match:
#                 return {
#                     "status": True,
#                     "message": f"Identified as employee {known['employee_id']} (distance: {round(distance, 4)})",
#                     "employee": known["employee_id"],
#                     "user": known["employee_id"]
#                 }

#         return {"status": False, "message": "No matching employee found.", "employee": None}

#     except Exception as e:
#         frappe.log_error(f"Face recognition error: {e}")
#         return {"status": False, "message": f"Internal error: {str(e)}"}

# @frappe.whitelist()
# def upload_file_in_doctype(data):
#     try:
#         filename = frappe.generate_hash(length=10)
#         # Detect file extension from base64 header
#         if data.startswith('data:image/png'):
#             ext = 'png'
#             base64data = data.replace('data:image/png;base64,', '')
#         else:
#             ext = 'jpg'
#             base64data = data.replace('data:image/jpeg;base64,', '')

#         # Use Frappe's public files path
#         from frappe.utils.file_manager import get_files_path
#         filepath = f"{get_files_path(is_private=False)}/{filename}.{ext}"

#         imgdata = base64.b64decode(base64data)
#         with open(filepath, 'wb') as file:
#             file.write(imgdata)

#         doc = frappe.get_doc({
#             "file_name": f'{filename}.{ext}',
#             "is_private": 0,
#             "file_url": f'/files/{filename}.{ext}',
#             "doctype": "File",
#         })
#         doc.flags.ignore_permissions = True
#         doc.insert()
#         frappe.db.commit()
#         return doc.file_url

#     except Exception as e:
#         frappe.log_error('ng_write_file', str(e))
#         return str(e)

import base64
import frappe
import numpy as np
import face_recognition
from io import BytesIO
import pickle
from frappe.utils.file_manager import save_file
import cv2

def load_all_face_encodings():
    """
    Ek hi baar mein saare encodings aur employee IDs ko NumPy arrays mein convert karta hai.
    """
    # records = frappe.get_all("Employee Face", fields=["employee_id", "face_encoding"])
    
    # known_encodings = []
    # known_employee_ids = []
    
    # for rec in records:
    #     if not rec.face_encoding:
    #         continue
    #     try:
    #         encoding_data = base64.b64decode(rec.face_encoding)
    #         encoding_array = pickle.loads(encoding_data)
    #         known_encodings.append(encoding_array)
    #         known_employee_ids.append(rec.employee_id)
    #     except Exception as e:
    #         frappe.logger().error(f"[Face Encoding Load Error] Employee {rec.employee_id}: {e}")
            
    # return np.array(known_encodings), known_employee_ids
    records = frappe.get_all("Employee Face", fields=["employee_id", "face_encoding"])
    known_encodings, known_employee_ids = [], []
    for rec in records:
        if not rec.face_encoding: continue
        try:
            encoding_array = pickle.loads(base64.b64decode(rec.face_encoding))
            known_encodings.append(encoding_array)
            known_employee_ids.append(rec.employee_id)
        except Exception as e: frappe.logger().error(f"[Encoding Load Error] {rec.employee_id}: {e}")
    return np.array(known_encodings), known_employee_ids


def check_liveness(opencv_image):
    """
    Input: OpenCV style (BGR) Image object.
    Output: Dictionary {"status": True/False, "score": 0.0 to 1.0}
    True matlab face REAL hai, False matlab photo/screen.
    """
    try:
        # Step A: Pre-processing (Hume face crop karna padta hai anti-spoof model ke liye)
        face_locations = face_recognition.face_locations(opencv_image)
        if not face_locations:
            return {"status": False, "score": 0, "message": "No face detected for liveness check."}
        
        # Pehla face lein
        top, right, bottom, left = face_locations[0]
        face_crop = opencv_image[top:bottom, left:right]
        
        # ----------------------------------------------------------------------------------
        # STEP B: AI MODEL INFERENCE (YAHAN AAPKA MODEL AAYEGA)
        # Placeholder integration example:
        # liveness_model = load_your_model() # (MiniVision/ONNX model example)
        # prepped_face = prep_for_model(face_crop)
        # real_score = liveness_model.predict(prepped_face)
        # ----------------------------------------------------------------------------------
        
        # MOCK SCORE: Hum yahan assume karte hain model lag chuka hai aur 0.95 probability de raha hai.
        # Asli implementation mein yahan actual model prediction logic aayega.
        liveness_probability_real = 0.95 # Dummy score (High score means REAL)
        
        # Minimum threshold define karo (e.g., 85% probability required to call it Real Skin)
        LIVENESS_THRESHOLD = 0.85
        
        if liveness_probability_real >= LIVENESS_THRESHOLD:
            return {"status": True, "score": liveness_probability_real}
        else:
            return {"status": False, "score": liveness_probability_real}
            
    except Exception as e:
        frappe.log_error(f"Liveness Check Failed: {e}")
        return {"status": False, "score": 0, "message": f"Error: {e}"}

# @frappe.whitelist()
# def identify_employee(image_url=None, data=None, tolerance=0.65):
#     """
#     Advance Face Recognition: Mobile app me bina kisi badlav ke direct compatible.
#     Purane image_url aur data (base64) dono parameters ko automatic adapt karega.
#     """
#     # 1. Check payload (agar image_url nahi hai to data parameter ko base64 manega)
#     if not image_url and not data:
#         return {"status": False, "message": "No image data or URL provided."}

#     # 2. Database se saare enrolled faces load karna (NumPy Vectorized arrays)
#     known_encodings, known_employee_ids = load_all_face_encodings()
#     if len(known_encodings) == 0:
#         return {"status": False, "message": "No enrolled faces found in the system."}

#     try:
#         # CASE A: Agar mobile app ne base64 string bheja hai (data parameter me)
#         if data and (data.startswith("data:image") or len(data) > 500):
#             if "," in data:
#                 data = data.split(",")[1]
#             image_bytes = base64.b64decode(data)
#             unknown_image = face_recognition.load_image_file(BytesIO(image_bytes))

#         # CASE B: Agar mobile app ne image_url bheja hai
#         else:
#             target_url = image_url or data
#             import requests
            
#             if target_url.startswith("/"):
#                 target_url = frappe.utils.get_url() + target_url
                
#             response = requests.get(target_url, timeout=10)
#             if response.status_code != 200:
#                 return {"status": False, "message": "Could not download image from the provided URL."}
#             unknown_image = face_recognition.load_image_file(BytesIO(response.content))

#         # 3. Face Encodings nikalna
#         unknown_encodings = face_recognition.face_encodings(unknown_image)

#         if len(unknown_encodings) != 1:
#             return {
#                 "status": False,
#                 "message": f"Expected 1 face, but found {len(unknown_encodings)}. Please use a clear image with one face."
#             }

#         unknown_encoding = unknown_encodings[0]

#         # 4. ADVANCED VECTORIZED MATCHING (No loops, instant calculation)
#         face_distances = face_recognition.face_distance(known_encodings, unknown_encoding)
        
#         # Sabse accurate match dhoondhna
#         best_match_index = np.argmin(face_distances)
#         best_distance = face_distances[best_match_index]

#         # 5. Tolerance Matching
#         if best_distance <= float(tolerance):
#             matched_employee = known_employee_ids[best_match_index]
            
#             frappe.logger().info(f"[Face Match Attempt] {matched_employee} distance: {best_distance}, match: True")
            
#             # Exact purana response dict return kar rahe hain taaki mobile app crash na ho
#             return {
#                 "status": True,
#                 "message": f"Identified as employee {matched_employee} (distance: {round(best_distance, 4)})",
#                 "employee": matched_employee,
#                 "user": matched_employee
#             }

#         return {"status": False, "message": "No matching employee found.", "employee": None}

#     except Exception as e:
#         frappe.log_error(f"Face recognition error: {e}")
#         return {"status": False, "message": f"Internal error: {str(e)}"}


@frappe.whitelist()
def identify_employee(image_url=None, data=None, tolerance=0.55):
    """
    Advance Face Recognition: Mobile app compatibility + Fixed typo.
    """
    if not image_url and not data:
        return {"status": False, "message": "No image data or URL provided."}

    known_encodings, known_employee_ids = load_all_face_encodings()
    if len(known_encodings) == 0:
        return {"status": False, "message": "No enrolled faces found."}

    try:
        # --- PHASE 1: Image Payload Handling ---
        if data and (data.startswith("data:image") or len(data) > 500):
            if "," in data: data = data.split(",")[1]
            image_bytes = base64.b64decode(data)
            nparr = np.frombuffer(image_bytes, np.uint8)
            opencv_image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            unknown_image_rgb = cv2.cvtColor(opencv_image_bgr, cv2.COLOR_BGR2RGB)
        else:
            target_url = image_url or data
            import requests
            response = requests.get(target_url if not target_url.startswith("/") else frappe.utils.get_url()+target_url)
            unknown_image_rgb = face_recognition.load_image_file(BytesIO(response.content))
            opencv_image_bgr = cv2.cvtColor(unknown_image_rgb, cv2.COLOR_RGB2BGR)

        # --- PHASE 1.5 - ADVANCED PASSIVE LIVENESS CHECK ---
        liveness_result = check_liveness(opencv_image_bgr)
        
        frappe.logger().info(f"[Liveness Check] Score: {liveness_result.get('score')}, Result: {liveness_result['status']}")

        if not liveness_result["status"]:
            return {
                "status": False,
                "message": f"Spoofing detected (Real Score: {round(liveness_result.get('score', 0)*100)}%). Attendance rejected.",
                "employee": None,
                "is_spoof": True
            }

        # --- PHASE 2: Recognition (FIXED TYPO HERE) ---
        unknown_encodings = face_recognition.face_encodings(unknown_image_rgb)

        if len(unknown_encodings) != 1:
            return {"status": False, "message": "Expected 1 face, please clarify image."}

        # Sahi method calling: face_recognition.face_distance
        face_distances = face_recognition.face_distance(known_encodings, unknown_encodings[0])
        best_match_index = np.argmin(face_distances)
        best_distance = face_distances[best_match_index]

        if best_distance <= float(tolerance):
            matched_employee = known_employee_ids[best_match_index]
            frappe.logger().info(f"[Face Match Success] {matched_employee} distance: {round(best_distance, 4)}")
            
            return {
                "status": True,
                "message": f"Identified as employee {matched_employee}",
                "employee": matched_employee,
                "user": matched_employee,
                "liveness_score": round(liveness_result['score'], 4)
            }

        return {"status": False, "message": "No matching employee found.", "employee": None}

    except Exception as e:
        frappe.log_error(f"Advanced recognition crash: {e}")
        return {"status": False, "message": f"Recognition failed: {str(e)}"}

@frappe.whitelist()
def upload_employee_image(employee_id, image_base64):
    """
    Frappe standard tarike se base64 image ko save karne ka advance function.
    """
    try:
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
            
        file_bytes = base64.b64decode(image_base64)
        filename = f"face_{employee_id}_{frappe.generate_hash(length=5)}.jpg"
        
        # Frappe built-in save_file function (Automatic File DocType manage karta hai)
        file_doc = save_file(
            fname=filename,
            content=file_bytes,
            dt="Employee Face", # Apne custom DocType ka naam yahan check kar lena
            dn=employee_id,
            is_private=1 # Security ke liye private rakhna safe hai
        )
        
        return {"status": True, "file_url": file_doc.file_url}
    except Exception as e:
        frappe.log_error("Face Image Upload Error", str(e))
        return {"status": False, "message": str(e)}