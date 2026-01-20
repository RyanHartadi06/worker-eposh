#!/usr/bin/env python3
"""
Simple script to publish test messages to RabbitMQ
Usage: python test-publish.py
"""

import pika
import json

# RabbitMQ connection parameters
credentials = pika.PlainCredentials('guest', 'guest')
parameters = pika.ConnectionParameters(
    host='localhost',
    port=5672,
    credentials=credentials,
    heartbeat=600,
    blocked_connection_timeout=300
)

# Sample employee data
test_employees = [
    {
        "employee": {
            "name": "John Doe",
            "identity_number": "1234567890123456",
            "kib_number": "TEST001",
            "birth_date": {"ymd": "1990-01-01"},
            "photo": {"link": "https://example.com/photo1.jpg"},
            "regionals": [{"name": "Zona I", "slug": "zona-i"}]
        }
    },
    {
        "employee": {
            "name": "Jane Smith",
            "identity_number": "6543210987654321",
            "kib_number": "TEST002",
            "birth_date": {"ymd": "1992-05-15"},
            "photo": {"link": "https://example.com/photo2.jpg"},
            "regionals": [{"name": "Zona II", "slug": "zona-ii"}]
        }
    },
    {
        "employee": {
            "name": "Bob Wilson",
            "identity_number": "9876543210123456",
            "kib_number": "TEST003",
            "birth_date": {"ymd": "1988-12-20"},
            "photo": {"link": "https://example.com/photo3.jpg"},
            "regionals": [{"name": "Zona III", "slug": "zona-iii"}]
        }
    }
]

def publish_to_queue(queue_name, message):
    """Publish message to RabbitMQ queue"""
    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Declare queue
        channel.queue_declare(queue=queue_name, durable=True)
        
        # Publish message
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/json'
            )
        )
        
        print(f"✓ Published to {queue_name}: {message['employee']['name']}")
        
        connection.close()
        return True
        
    except Exception as e:
        print(f"✗ Error publishing: {e}")
        return False

if __name__ == "__main__":
    print("=== Testing RabbitMQ Pub/Sub ===\n")
    
    # Test 1: Publish single employee
    print("1. Publishing single employee to CREATE_PERSON queue...")
    publish_to_queue('hikvision_create_person', test_employees[0])
    print()
    
    # Test 2: Publish multiple employees
    print("2. Publishing 3 employees to CREATE_PERSON queue...")
    for employee_data in test_employees:
        publish_to_queue('hikvision_create_person', employee_data)
    
    print("\n=== Done! ===")
    print("Check worker logs: docker-compose logs -f worker-pubsub")
    print("Check RabbitMQ UI: http://localhost:15672 (guest/guest)")
