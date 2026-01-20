#!/bin/bash

# Test Publishing to RabbitMQ via Management API
# RabbitMQ Management API: http://localhost:15672

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

RABBITMQ_HOST="localhost"
RABBITMQ_PORT="15672"
RABBITMQ_USER="guest"
RABBITMQ_PASS="guest"

echo -e "${YELLOW}=== Testing RabbitMQ Pub/Sub ===${NC}\n"

# Test 1: Publish to CREATE_PERSON queue (Single Employee)
echo -e "${GREEN}1. Publishing single employee to CREATE_PERSON queue...${NC}"

curl -i -u ${RABBITMQ_USER}:${RABBITMQ_PASS} \
  -H "Content-Type: application/json" \
  -X POST http://${RABBITMQ_HOST}:${RABBITMQ_PORT}/api/exchanges/%2F/amq.default/publish \
  -d '{
    "properties": {
      "delivery_mode": 2,
      "content_type": "application/json"
    },
    "routing_key": "hikvision_create_person",
    "payload": "{\"employee\": {\"name\": \"John Doe Test\", \"identity_number\": \"1234567890123456\", \"kib_number\": \"TEST001\", \"birth_date\": {\"ymd\": \"1990-01-01\"}, \"photo\": {\"link\": \"https://example.com/photo.jpg\"}, \"regionals\": [{\"name\": \"Zona I\", \"slug\": \"zona-i\"}]}}",
    "payload_encoding": "string"
  }'

echo -e "\n"

# Test 2: Publish multiple employees
echo -e "${GREEN}2. Publishing 3 employees to CREATE_PERSON queue...${NC}"

for i in {1..3}; do
  echo "Publishing employee $i..."
  curl -s -u ${RABBITMQ_USER}:${RABBITMQ_PASS} \
    -H "Content-Type: application/json" \
    -X POST http://${RABBITMQ_HOST}:${RABBITMQ_PORT}/api/exchanges/%2F/amq.default/publish \
    -d "{
      \"properties\": {
        \"delivery_mode\": 2,
        \"content_type\": \"application/json\"
      },
      \"routing_key\": \"hikvision_create_person\",
      \"payload\": \"{\\\"employee\\\": {\\\"name\\\": \\\"Employee Test $i\\\", \\\"identity_number\\\": \\\"TEST$i\\\", \\\"kib_number\\\": \\\"KIB00$i\\\", \\\"birth_date\\\": {\\\"ymd\\\": \\\"1990-01-0$i\\\"}, \\\"photo\\\": {\\\"link\\\": \\\"https://example.com/photo$i.jpg\\\"}, \\\"regionals\\\": [{\\\"name\\\": \\\"Zona II\\\", \\\"slug\\\": \\\"zona-ii\\\"}]}}\",
      \"payload_encoding\": \"string\"
    }"
  echo "✓ Employee $i published"
done

echo -e "\n${YELLOW}=== Check Queue Status ===${NC}"

# Check queue status
curl -s -u ${RABBITMQ_USER}:${RABBITMQ_PASS} \
  http://${RABBITMQ_HOST}:${RABBITMQ_PORT}/api/queues/%2F/hikvision_create_person | \
  python3 -c "import sys, json; data = json.load(sys.stdin); print(f'Messages: {data.get(\"messages\", 0)}')"

echo -e "\n${GREEN}Done! Check worker logs:${NC}"
echo "docker-compose logs -f worker-pubsub"
