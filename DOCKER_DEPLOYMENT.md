# Hikvision Worker - Docker Deployment

## Docker Architecture

```
┌─────────────────────────┐
│   RabbitMQ Container    │
│   Port: 5672, 15672     │
└──────────┬──────────────┘
           │
           ├──────────────┐
           │              │
           ▼              ▼
┌──────────────────┐   ┌──────────────────┐
│  Flask App       │   │  Worker Pub/Sub  │
│  (app.py)        │   │  (3 workers)     │
│  Port: 5000      │   │                  │
└──────────────────┘   └──────────────────┘
```

## Files Structure

```
worker-eposh/
├── docker-compose.yml
├── Dockerfile.flask
├── Dockerfile.worker
├── requirements.txt
├── app.py
├── worker_pubsub.py
├── worker.py
├── config.py
├── rabbitmq.py
└── .env
```

## Quick Start

### 1. Build and Run All Services

```bash
docker-compose up --build
```

### 2. Run in Background

```bash
docker-compose up -d
```

### 3. View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f flask-app
docker-compose logs -f worker-pubsub
docker-compose logs -f rabbitmq
```

### 4. Stop All Services

```bash
docker-compose down
```

## Configuration Files

### 1. docker-compose.yml

```yaml
version: '3.8'

services:
  # RabbitMQ Service
  rabbitmq:
    image: rabbitmq:3-management
    container_name: hikvision-rabbitmq
    ports:
      - "5672:5672"    # AMQP port
      - "15672:15672"  # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-guest}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-guest}
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - hikvision-network

  # Flask App
  flask-app:
    build:
      context: .
      dockerfile: Dockerfile.flask
    container_name: hikvision-flask
    ports:
      - "5000:5000"
    environment:
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_PORT=5672
      - RABBITMQ_USER=${RABBITMQ_USER:-guest}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-guest}
    depends_on:
      rabbitmq:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - hikvision-network

  # Worker Pub/Sub (3 workers in 1 container)
  worker-pubsub:
    build:
      context: .
      dockerfile: Dockerfile.worker
    container_name: hikvision-worker-pubsub
    environment:
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_PORT=5672
      - RABBITMQ_USER=${RABBITMQ_USER:-guest}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD:-guest}
    depends_on:
      rabbitmq:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - hikvision-network
    # Scale this service if needed
    deploy:
      replicas: 1

networks:
  hikvision-network:
    driver: bridge

volumes:
  rabbitmq-data:
```

### 2. Dockerfile.flask

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY config.py .
COPY rabbitmq.py .
COPY worker.py .

# Expose Flask port
EXPOSE 5000

# Run Flask app
CMD ["python", "app.py"]
```

### 3. Dockerfile.worker

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY worker_pubsub.py .
COPY worker.py .
COPY config.py .

# Run worker pub/sub
CMD ["python", "worker_pubsub.py"]
```

### 4. .env

```env
# RabbitMQ Configuration
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

# Eposh API
EPOSH_API_URL=https://gcp-api.eposh.id/v1/induction/employees
EPOSH_API_KEY=4237aa07-376f-4db9-9c83-9cf91dc6438f
EPOSH_APP_ID=hcpvision

# Hikvision API
HIKVISION_BASE_URL=https://192.168.100.15
HIKVISION_AK=26295356
HIKVISION_SIGNATURE=oXTtrB6HCLlaqF6bqMXL
```

### 5. requirements.txt

```txt
Flask==3.0.0
pika==1.3.2
requests==2.31.0
python-dotenv==1.0.0
urllib3==2.1.0
```

## Usage

### Step 1: Start All Services

```bash
docker-compose up -d
```

Output:
```
Creating network "hikvision-network" with driver "bridge"
Creating hikvision-rabbitmq ... done
Creating hikvision-flask ... done
Creating hikvision-worker-pubsub ... done
```

### Step 2: Check Services Status

```bash
docker-compose ps
```

Output:
```
NAME                      STATUS              PORTS
hikvision-rabbitmq        Up (healthy)        0.0.0.0:5672->5672/tcp, 0.0.0.0:15672->15672/tcp
hikvision-flask           Up                  0.0.0.0:5000->5000/tcp
hikvision-worker-pubsub   Up
```

### Step 3: Access Services

1. **Flask API**: http://localhost:5000
2. **RabbitMQ Management UI**: http://localhost:15672 (guest/guest)

### Step 4: Trigger Sync

```bash
curl -X POST http://localhost:5000/eposh-induction
```

### Step 5: Monitor Logs

```bash
# Watch all logs
docker-compose logs -f

# Watch specific service
docker-compose logs -f worker-pubsub
```

Output:
```
worker-pubsub | [CREATE PERSON] Starting worker...
worker-pubsub | [UPDATE KIB] Starting worker...
worker-pubsub | [ASSIGN PRIVILEGE] Starting worker...
worker-pubsub | All workers started successfully!
worker-pubsub | [CREATE PERSON] Processing: John Doe
worker-pubsub | ✓ Employee John Doe sent successfully
```

## Scaling Workers

### Scale Worker Pub/Sub to 3 Instances

```bash
docker-compose up -d --scale worker-pubsub=3
```

This will run 3 containers of worker-pubsub, each with 3 internal workers = 9 workers total!

```
worker-pubsub-1:
  - Worker CREATE_PERSON
  - Worker UPDATE_KIB
  - Worker ASSIGN_PRIVILEGE

worker-pubsub-2:
  - Worker CREATE_PERSON
  - Worker UPDATE_KIB
  - Worker ASSIGN_PRIVILEGE

worker-pubsub-3:
  - Worker CREATE_PERSON
  - Worker UPDATE_KIB
  - Worker ASSIGN_PRIVILEGE
```

## Production Deployment

### docker-compose.prod.yml

```yaml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3-management
    container_name: hikvision-rabbitmq-prod
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: always
    networks:
      - hikvision-network

  flask-app:
    build:
      context: .
      dockerfile: Dockerfile.flask
    container_name: hikvision-flask-prod
    ports:
      - "5000:5000"
    environment:
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_PORT=5672
      - RABBITMQ_USER=${RABBITMQ_USER}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}
      - FLASK_ENV=production
    depends_on:
      rabbitmq:
        condition: service_healthy
    restart: always
    networks:
      - hikvision-network

  worker-pubsub:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - RABBITMQ_HOST=rabbitmq
      - RABBITMQ_PORT=5672
      - RABBITMQ_USER=${RABBITMQ_USER}
      - RABBITMQ_PASSWORD=${RABBITMQ_PASSWORD}
    depends_on:
      rabbitmq:
        condition: service_healthy
    restart: always
    networks:
      - hikvision-network
    deploy:
      replicas: 3  # 3 instances

networks:
  hikvision-network:
    driver: bridge

volumes:
  rabbitmq-data:
    driver: local
```

**Run Production:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### 1. RabbitMQ Connection Refused

```bash
# Check RabbitMQ is running
docker-compose ps rabbitmq

# Check RabbitMQ logs
docker-compose logs rabbitmq

# Restart RabbitMQ
docker-compose restart rabbitmq
```

### 2. Workers Not Processing

```bash
# Check worker logs
docker-compose logs -f worker-pubsub

# Restart workers
docker-compose restart worker-pubsub
```

### 3. Check Queue Status

Access RabbitMQ Management UI:
- URL: http://localhost:15672
- Login: guest/guest
- Go to "Queues" tab

### 4. Container Networking Issues

```bash
# Inspect network
docker network inspect worker-eposh_hikvision-network

# Test connection from flask to rabbitmq
docker-compose exec flask-app ping rabbitmq
```

### 5. Rebuild Containers

```bash
# Rebuild all containers
docker-compose build --no-cache

# Rebuild and restart
docker-compose up -d --build
```

## Monitoring

### View Resource Usage

```bash
docker stats
```

Output:
```
CONTAINER ID   NAME                        CPU %     MEM USAGE
abc123         hikvision-rabbitmq          2.5%      150MB
def456         hikvision-flask             0.5%      80MB
ghi789         hikvision-worker-pubsub     1.2%      100MB
```

### Export Logs to File

```bash
docker-compose logs > logs.txt
```

## Backup & Restore

### Backup RabbitMQ Data

```bash
# Create backup
docker run --rm --volumes-from hikvision-rabbitmq \
  -v $(pwd):/backup ubuntu \
  tar czf /backup/rabbitmq-backup.tar.gz /var/lib/rabbitmq

# Restore backup
docker run --rm --volumes-from hikvision-rabbitmq \
  -v $(pwd):/backup ubuntu \
  tar xzf /backup/rabbitmq-backup.tar.gz
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| RABBITMQ_HOST | rabbitmq | RabbitMQ hostname |
| RABBITMQ_PORT | 5672 | RabbitMQ AMQP port |
| RABBITMQ_USER | guest | RabbitMQ username |
| RABBITMQ_PASSWORD | guest | RabbitMQ password |
| FLASK_ENV | development | Flask environment |

## Network Ports

| Port | Service | Description |
|------|---------|-------------|
| 5000 | Flask App | HTTP API |
| 5672 | RabbitMQ | AMQP Protocol |
| 15672 | RabbitMQ | Management UI |

## Health Checks

### Flask Health Check

```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "status": "ok"
}
```

### RabbitMQ Health Check

```bash
curl -u guest:guest http://localhost:15672/api/health/checks/alarms
```

## Commands Cheat Sheet

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart a service
docker-compose restart flask-app

# View logs
docker-compose logs -f worker-pubsub

# Scale workers
docker-compose up -d --scale worker-pubsub=5

# Execute command in container
docker-compose exec flask-app bash

# Rebuild and restart
docker-compose up -d --build

# Remove all containers and volumes
docker-compose down -v

# Check status
docker-compose ps
```

## Complete Setup Example

```bash
# 1. Clone repository
git clone https://github.com/your-repo/worker-eposh.git
cd worker-eposh

# 2. Create .env file
cat > .env << EOF
RABBITMQ_USER=admin
RABBITMQ_PASSWORD=secretpassword
EOF

# 3. Build and start
docker-compose up -d --build

# 4. Wait for services to be ready (30 seconds)
sleep 30

# 5. Check status
docker-compose ps

# 6. Trigger sync
curl -X POST http://localhost:5000/eposh-induction

# 7. Monitor logs
docker-compose logs -f worker-pubsub

# 8. Access RabbitMQ UI
echo "Open http://localhost:15672 in browser"
```

That's it! Your Hikvision worker system is now running in Docker containers! 🚀
