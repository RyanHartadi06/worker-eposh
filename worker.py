import base64
import hashlib
import hmac
from inspect import signature
import json
import pika
import requests
import urllib3
from config import (HIKVISION_AK, HIKVISION_SIGNATURE, RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD, QUEUE_NAME, HIKVISION_BASE_URL, QUEUE_CREATE_PERSON)

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def download_photo_as_base64(photo_url):
    """Download photo from URL and convert to base64"""
    try:
        response = requests.get(photo_url, verify=False, timeout=10)
        response.raise_for_status()
        return base64.b64encode(response.content).decode('utf-8')
    except Exception as e:
        print(f"✗ Error downloading photo from {photo_url}: {e}")
        return ""

def generate_signature(method, accept, content_type, url_path, app_secret):
    """Generate X-Ca-Signature using HMAC-SHA256"""
    text_to_sign = f"{method}\n{accept}\n{content_type}\n{url_path}"
    hash_obj = hmac.new(
        app_secret.encode('utf-8'),
        text_to_sign.encode('utf-8'),
        hashlib.sha256
    )
    signature = base64.b64encode(hash_obj.digest()).decode('utf-8')
    return signature

def send_to_hikvision(employee: dict):
    """Send single employee data to Hikvision"""
    print(f"Processing employee: {employee.get('name')} (KIB: {employee.get('kib_number')})")
    
    url = "https://192.168.100.15:443/artemis/api/resource/v1/person/single/add"
    method = "POST"
    accept = "application/json"
    content_type = "application/json;charset=UTF-8"
    url_path = "/artemis/api/resource/v1/person/single/add"
    app_secret = "oXTtrB6HCLlaqF6bqMXL"
    
    # Generate signature
    signature = generate_signature(method, accept, content_type, url_path, app_secret)
    
    headers = {
        "Content-Type": content_type,
        "Accept": accept,
        "X-Ca-Key": "26295356",
        "X-Ca-Signature": signature,
    }
    
    # Download and convert photo to base64
    photo_base64 = ""
    if "photo" in employee and employee["photo"]:
        photo_link = employee["photo"].get("link", "")
        if photo_link:
            photo_base64 = download_photo_as_base64(photo_link)
    
    # Map regionals from Eposh to HCP privilege groups
    regional_mapping = {
        "zona-i": "1",      # Access Gate Zona 1
        "zona-ii": "2",     # Access Gate Zona 2
        "zona-iii": "6",    # Access Gate Zona 3
        "zona-iv": "7",     # Access Gate Zona 4
        "tuks": "8",        # Access Gate TUKS
        "kawasan": "9"      # Access Gate Kawasan
    }
    
    # Get privilege groups based on employee's regionals
    privilege_groups = []
    regionals = employee.get("regionals", [])
    for regional in regionals:
        slug = regional.get("slug", "")
        if slug in regional_mapping:
            privilege_groups.append(regional_mapping[slug])
    
    print(f"Mapped regionals: {[r.get('name') for r in regionals]} → Privilege Groups: {privilege_groups}")
    
    payload = {
        "personCode": employee.get("identity_number"),
        "personFamilyName": " ",
        "personGivenName": employee.get("name"),
        "gender": 1,
        "orgIndexCode": "84",
        "remark": "From Eposh Induction",
        "phoneNo": employee.get("phone_number", "0000000000"),
        "email": employee.get("email", "xxx@gmail.com"),
        "faces": [
            {
                "faceData": photo_base64,
            }
        ],
        "beginTime": "2026-01-05T00:00:00+08:00",
        "endTime": "2030-12-31T23:59:59+08:00"
    }
    
    # Add privilege groups if any
    if privilege_groups:
        payload["privilegeGroupIds"] = ",".join(privilege_groups)
    
    try:
        response = requests.post(url, json=payload, headers=headers, verify=False)
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")
        response.raise_for_status()
        print(f"✓ Employee {employee.get('name')} sent successfully")
        response_json = response.json()
        # Extract personId from response - data field contains the ID as a string
        person_id = response_json.get("data")
        return {"personId": person_id, "response": response_json}
    except Exception as e:
        print(f"✗ Error sending employee {employee.get('name')}: {e}")
        return None

def assign_privilege_groups(personId, privilege_group_ids):
    """Assign privilege groups to a person"""
    print(f"Assigning privilege groups {privilege_group_ids} to person ID {personId}")
    if not privilege_group_ids:
        print(f"No privilege groups to assign for person ID {personId}")
        return True
    
    url = "https://192.168.100.15:443/artemis/api/acs/v1/privilege/group/single/addPersons"
    method = "POST"
    accept = "application/json"
    content_type = "application/json;charset=UTF-8"
    url_path = "/artemis/api/acs/v1/privilege/group/single/addPersons"
    app_secret = "oXTtrB6HCLlaqF6bqMXL"
    
    success_count = 0
    for group_id in privilege_group_ids:
        # Generate signature
        text_to_sign = f"{method}\n{accept}\n{content_type}\n{url_path}"
        signature = generate_signature(method, accept, content_type, url_path, app_secret)
        
        headers = {
            "Content-Type": content_type,
            "Accept": accept,
            "X-Ca-Key": "26295356",
            "X-Ca-Signature": signature,
        }
        
        payload = {
            "privilegeGroupId": group_id,
            "type": 1,
            "list": [
                {
                    "id": personId
                }
            ]
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, verify=False)
            print(f"Privilege Group {group_id} - Status: {response.status_code}")
            print(f"Response: {response.text}")
            response.raise_for_status()
            print(f"✓ Person {personId} added to privilege group {group_id}")
            success_count += 1
        except Exception as e:
            print(f"✗ Error adding person {personId} to privilege group {group_id}: {e}")
    
    print(f"Assigned {success_count}/{len(privilege_group_ids)} privilege groups to person {personId}")
    return success_count > 0

def update_employee_kib(personId, kib_number):
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
        "personId": personId,
        "list": [
            {
                "id": "1",
                "customFiledName": "KIB",
                "customFieldType": 1,
                "customFieldValue": kib_number
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
        print(f"✓ Employee ID {personId} updated with KIB {kib_number}")
        return True
    except Exception as e:
        print(f"✗ Error updating employee ID {personId}: {e}")
        return False
        
def callback_pubsub(ch, method, properties, body):
    """Callback for pub/sub mode - publishes to CREATE_PERSON queue"""
    try:
        message = json.loads(body)
        response_data = message.get("data")
        
        # Extract employee list from response
        employees = response_data.get("data", [])
        pagination = response_data.get("pagination", {})
        
        print(f"\n{'='*60}")
        print(f"Received batch: Page {pagination.get('current_page')}/{pagination.get('last_page')}")
        print(f"Publishing {len(employees)} employees to CREATE_PERSON queue...")
        print(f"{'='*60}\n")
        
        # Publish each employee to CREATE_PERSON queue
        success_count = 0
        for employee in employees:
            try:
                # Publish to CREATE_PERSON queue
                employee_message = {
                    "employee": employee
                }
                
                ch.basic_publish(
                    exchange='',
                    routing_key=QUEUE_CREATE_PERSON,
                    body=json.dumps(employee_message),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                
                print(f"Published: {employee.get('name')} (KIB: {employee.get('kib_number')})")
                success_count += 1
            except Exception as e:
                print(f"Failed to publish employee {employee.get('name')}: {e}")
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"\n✓ Batch published: {success_count}/{len(employees)} employees sent to CREATE_PERSON queue\n")
        
    except Exception as e:
        print(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        response_data = message.get("data")
        
        # Extract employee list from response
        employees = response_data.get("data", [])
        pagination = response_data.get("pagination", {})
        
        print(f"\n{'='*60}")
        print(f"Received batch: Page {pagination.get('current_page')}/{pagination.get('last_page')}")
        print(f"Processing {len(employees)} employees...")
        print(f"{'='*60}\n")
        
        # Process each employee
        success_count = 0
        for employee in employees:
            try:
                result = send_to_hikvision(employee)
                if result:
                    person_id = result.get("personId")
                    print(f"Received Person ID: {person_id}")
                    kib_number = employee.get("kib_number")
                    
                    # Update KIB custom field
                    if person_id and kib_number:
                        update_employee_kib(person_id, kib_number)
                    
                    # Assign privilege groups
                    if person_id:
                        # Map regionals to privilege groups
                        regional_mapping = {
                            "zona-i": "1",
                            "zona-ii": "2",
                            "zona-iii": "6",
                            "zona-iv": "7",
                            "tuks": "8",
                            "kawasan": "9"
                        }
                        
                        privilege_groups = []
                        regionals = employee.get("regionals", [])
                        for regional in regionals:
                            slug = regional.get("slug", "")
                            if slug in regional_mapping:
                                privilege_groups.append(regional_mapping[slug])
                        
                        if privilege_groups:
                            assign_privilege_groups(person_id, privilege_groups)
                    
                success_count += 1
            except Exception as e:
                print(f"Failed to process employee: {e}")
                # Continue with next employee
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"\n✓ Batch completed: {success_count}/{len(employees)} employees processed\n")
        
    except Exception as e:
        print(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)  
        
def start_worker():
    print("Starting worker...")
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    
    # Add heartbeat and timeout settings to prevent connection loss
    connection_params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=600,  # 10 minutes heartbeat
        blocked_connection_timeout=300  # 5 minutes timeout
    )
    
    connection = pika.BlockingConnection(connection_params)
    
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
    
    print(f"Worker started. Waiting for messages on queue: {QUEUE_NAME}...")
    channel.start_consuming()
    
if __name__ == "__main__":
    start_worker()