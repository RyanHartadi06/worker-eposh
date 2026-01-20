@echo off
REM Test Publishing to RabbitMQ via Management API
REM RabbitMQ Management API: http://localhost:15672

set RABBITMQ_HOST=localhost
set RABBITMQ_PORT=15672
set RABBITMQ_USER=guest
set RABBITMQ_PASS=guest

echo === Testing RabbitMQ Pub/Sub ===
echo.

echo 1. Publishing single employee to CREATE_PERSON queue...
curl -u %RABBITMQ_USER%:%RABBITMQ_PASS% ^
  -H "Content-Type: application/json" ^
  -X POST http://%RABBITMQ_HOST%:%RABBITMQ_PORT%/api/exchanges/%%2F/amq.default/publish ^
  -d "{\"properties\": {\"delivery_mode\": 2, \"content_type\": \"application/json\"}, \"routing_key\": \"hikvision_create_person\", \"payload\": \"{\\\"employee\\\": {\\\"name\\\": \\\"John Doe Test\\\", \\\"identity_number\\\": \\\"1234567890123456\\\", \\\"kib_number\\\": \\\"TEST001\\\", \\\"birth_date\\\": {\\\"ymd\\\": \\\"1990-01-01\\\"}, \\\"photo\\\": {\\\"link\\\": \\\"https://example.com/photo.jpg\\\"}, \\\"regionals\\\": [{\\\"name\\\": \\\"Zona I\\\", \\\"slug\\\": \\\"zona-i\\\"}]}}\", \"payload_encoding\": \"string\"}"

echo.
echo.
echo === Check Worker Logs ===
echo Run: docker-compose logs -f worker-pubsub
echo.
pause
