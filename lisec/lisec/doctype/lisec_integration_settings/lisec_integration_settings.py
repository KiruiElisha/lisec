# Copyright (c) 2024, Codes Soft and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests
from urllib3.exceptions import InsecureRequestWarning
import json

class LisecIntegrationSettings(Document):
	pass

@frappe.whitelist()
def test_connection():
	try:
		settings = frappe.get_single('Lisec Integration Settings')
		
		# Disable SSL warning
		requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
		
		# Construct the base URL using the format from integration tool
		base_url = f"https://{settings.lisec_ip_address}:{settings.lisec_ip_port}/api/sites/{settings.site}/versions/1"
		
		# First try to get access token
		url = base_url + "/authentication/tokens"
		
		# Try refresh token first if available
		if settings.api_refresh_token:
			req_header = {"refreshTokenHeader": settings.api_refresh_token}
			resp = requests.put(url, headers=req_header, verify=False)
			
			if resp.status_code == 200:
				return {"success": True, "message": "Successfully connected using refresh token"}
		
		# If refresh token fails or not available, try user/password
		if settings.api_user and settings.api_password_hash:
			req_header = {
				"userHeader": settings.api_user,
				"passwordHeader": settings.api_password_hash
			}
			
			resp = requests.post(url, headers=req_header, verify=False)
			
			if resp.status_code == 200:
				result = resp.json()
				return {
					"success": True,
					"message": "Successfully connected using user credentials",
					"refresh_token": result.get("refreshToken")
				}
			else:
				return {
					"success": False,
					"error": f"Authentication failed: {resp.status_code} - {resp.reason}"
				}
		else:
			return {
				"success": False,
				"error": "No authentication credentials provided"
			}
			
	except requests.exceptions.ConnectionError:
		return {
			"success": False,
			"error": "Connection Error: Unable to connect to the Lisec server"
		}
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}
