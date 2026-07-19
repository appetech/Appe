# # Copyright (c) 2026, Appe Technologies and contributors
# # For license information, please see license.txt

# from io import BytesIO
# import frappe
# from frappe.model.document import Document
# import face_recognition
# import requests
# import numpy as np
# import pickle
# import base64



# class EmployeeFace(Document):
    
    
# 	def before_save(self):
# 		try:
# 			face_image_path = self.face_image
# 			employee_id = self.employee_id

# 			if not face_image_path:
# 				frappe.msgprint("No face image found.")
# 				return

# 			# Construct full image URL
# 			site_url = frappe.utils.get_url()
# 			full_url = f"{site_url}{face_image_path}"

# 			# Download image
# 			response = requests.get(full_url)
# 			if response.status_code != 200:
# 				frappe.throw(f"Could not download image for employee {employee_id}")

# 			# Load image into memory (no need to save temp file)
# 			image = face_recognition.load_image_file(BytesIO(response.content))
# 			encodings = face_recognition.face_encodings(image)

# 			if not encodings:
# 				frappe.throw("No face detected in image.")

# 			encoding = encodings[0]

# 			# Save face encoding as base64(pickle)
# 			encoded_bytes = pickle.dumps(encoding)
# 			self.face_encoding = base64.b64encode(encoded_bytes).decode('utf-8')

# 			frappe.logger().info(f"✅ Face enrolled for {employee_id}")

# 		except Exception as e:
# 			frappe.log_error("Enroll Employee Error", f"❌ Error enrolling face for {self.employee_id}: {e}")
# 			frappe.throw(f"Face enrollment failed: {e}")
    
# Copyright (c) 2026, Appe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import face_recognition
import numpy as np
import pickle
import base64
import os
from io import BytesIO

class EmployeeFace(Document):
    
    def before_save(self):
        try:
            if not self.face_image:
                frappe.throw("Please upload a face image first.")

            # Agar image local paths (/files/...) se hai toh requests.get lagane ki jarurat nahi hai
            # Direct server path se uthao, fast chalega
            file_url = self.face_image
            
            if file_url.startswith("/files/") or file_url.startswith("/private/files/"):
                # Frappe unique method to get local file absolute path
                public_path = frappe.get_site_path("public" if "private" not in file_url else "", file_url.lstrip("/"))
                
                if not os.path.exists(public_path):
                    frappe.throw(f"File path not found on server: {public_path}")
                    
                image = face_recognition.load_image_file(public_path)
            else:
                # Agar external image URL hai tabhi requests use karo
                import requests
                site_url = frappe.utils.get_url()
                full_url = f"{site_url}{file_url}" if file_url.startswith("/") else file_url
                
                response = requests.get(full_url, timeout=10)
                if response.status_code != 200:
                    frappe.throw(f"Unable to download image from: {full_url}")
                image = face_recognition.load_image_file(BytesIO(response.content))

            # Face Encodings nikalna
            encodings = face_recognition.face_encodings(image)

            if not encodings:
                frappe.throw("No face detected in the uploaded image. Please ensure proper lighting and face alignment.")
            
            if len(encodings) > 1:
                frappe.throw("Multiple faces detected! Please upload an image with exactly one clear face.")

            # Save the first face encoding
            encoding = encodings[0]
            encoded_bytes = pickle.dumps(encoding)
            self.face_encoding = base64.b64encode(encoded_bytes).decode('utf-8')

            frappe.logger().info(f"✅ Advanced Face Enrollment complete for Employee: {self.employee_id}")

        except Exception as e:
            frappe.log_error("Enroll Employee Error", f"Error code: {str(e)}")
            frappe.throw(f"Face enrollment failed: {str(e)}")