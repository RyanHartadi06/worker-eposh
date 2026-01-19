from flask import Flask, request, jsonify
from config import HIKVISION_AK, HIKVISION_BASE_URL, HIKVISION_SIGNATURE
from rabbitmq import publish_message
from worker import generate_signature, send_to_hikvision
import requests
import urllib3

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@app.route("/kib", methods=["POST"])
def endpointKib():
    """Update employee record with KIB number"""
    url = "https://192.168.100.15:443/artemis/api/resource/v1/person/personId/customFieldsUpdate"
    method = "POST"
    accept = "application/json"
    content_type = "application/json;charset=UTF-8"
    url_path = "/artemis/api/resource/v1/person/personId/customFieldsUpdate"
    app_secret = "oXTtrB6HCLlaqF6bqMXL"
    
    # Generate signature
    text_to_sign = f"{method}\n{accept}\n{content_type}\n{url_path}"
    print(f"Text to Sign:\n{text_to_sign}")
    signature = generate_signature(method, accept, content_type, url_path, app_secret)
    print(f"Generated Signature: {signature}")
    
    headers = {
        "Content-Type": content_type,
        "Accept": accept,
        "X-Ca-Key": "26295356",
        "X-Ca-Signature": signature,
    }
    
    payload = {
        "personId": "16863",
        "list": [
            {
                "id": "1",
                "customFiledName": "KIB",
                "customFieldType": 1,
                "customFieldValue": "12312312321"
            }
        ]
    }
    
    try:
        session = requests.Session()
        session.verify = False
        response = session.post(url, json=payload, headers=headers)
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")
        response.raise_for_status()
        print(f"✓ Employee ID updated with KIB k23012312312")
        return jsonify({"success": True, "response": response.json()}), 200
    except Exception as e:
        print(f"✗ Error updating employee ID: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# @app.route("/send-to-hikvision", methods=["POST"])
# def send_to_hikvision_route():
#     payload = request.json

#     if not payload:
#         return jsonify({"error": "Invalid payload"}), 400

#     message = {
#         "event": "HIKVISION_SYNC",
#         "data": payload
#     }

#     publish_message(message)

#     return jsonify({
#         "status": "queued",
#         "message": "Data sent to RabbitMQ"
#     }), 202
    
@app.route("/eposh-induction", methods=["POST"])
def endpointEposh():
    try:
        base_url = "https://gcp-api.eposh.id/v1/induction/employees"
        headers = {
            "x-api-key": "4237aa07-376f-4db9-9c83-9cf91dc6438f",
            "x-app-id": "hcpvision",
        }
        
        # Loop through dates from Jan 1 to Jan 19, 2026 (skip Jan 2 and Jan 5)
        skip_dates = [2, 5]
        total_employees_queued = 0
        total_pages_queued = 0
        
        for day in range(1, 20):  # 1 to 19
            if day in skip_dates:
                print(f"Skipping January {day}, 2026")
                continue
            
            induction_date = f"2026-01-{day:02d}"  # Format: 2026-01-01, 2026-01-03, etc.
            print(f"\n{'='*60}")
            print(f"Processing induction date: {induction_date}")
            print(f"{'='*60}")
            
            # Fetch first page to get pagination info
            params = {
                "induction_date": induction_date,
                "include_base64": "false",
                "page": 1,
                "limit": 100
            }
            
            response = requests.get(base_url, headers=headers, params=params, verify=False)
            response.raise_for_status()
            first_page = response.json()
            
            pagination = first_page.get("pagination", {})
            total_pages = pagination.get("last_page", 1)
            total_records = pagination.get("total", 0)
            
            if total_records == 0:
                print(f"No employees found for {induction_date}")
                continue
            
            print(f"Found {total_records} employees across {total_pages} pages for {induction_date}")
            
            # Send first page to RabbitMQ
            message = {
                "event": "HIKVISION_SYNC",
                "data": first_page
            }
            publish_message(message)
            total_employees_queued += len(first_page.get("data", []))
            total_pages_queued += 1
            
            # Send remaining pages to RabbitMQ
            for page in range(2, total_pages + 1):
                params["page"] = page
                response = requests.get(base_url, headers=headers, params=params, verify=False)
                response.raise_for_status()
                page_data = response.json()
                
                message = {
                    "event": "HIKVISION_SYNC",
                    "data": page_data
                }
                publish_message(message)
                total_employees_queued += len(page_data.get("data", []))
                total_pages_queued += 1
                print(f"  Page {page}/{total_pages} queued for {induction_date}")
            
            print(f"✓ Completed {induction_date}: {total_records} employees queued")
        
        return jsonify({
            "status": "queued",
            "message": f"All dates processed: {total_employees_queued} employees across {total_pages_queued} pages sent to RabbitMQ"
        }), 202
        
    except Exception as e:
        print(f"Error in eposh-induction endpoint: {e}")
        return jsonify({"error": str(e)}), 500
  
if __name__ == "__main__":
    app.run(debug=True, port=5000)