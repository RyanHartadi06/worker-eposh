# Hikvision Worker - Pub/Sub System

## Architecture

```
┌─────────────────┐
│  Flask Endpoint │
│ /eposh-induction│
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│   RabbitMQ Queue        │
│   hikvision_queue       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Publisher Worker      │
│   (worker.py)           │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   CREATE_PERSON Queue   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Worker 1              │
│   Create Person         │
│   (worker_pubsub.py)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   UPDATE_KIB Queue      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Worker 2              │
│   Update KIB Field      │
│   (worker_pubsub.py)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  ASSIGN_PRIVILEGE Queue │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Worker 3              │
│   Assign Privilege      │
│   (worker_pubsub.py)    │
└─────────────────────────┘
```

## How to Run

### 1. Start RabbitMQ Server
```bash
# Make sure RabbitMQ is running
# Default: localhost:5672
```

### 2. Start Pub/Sub Workers (3 workers in parallel)
```bash
python worker_pubsub.py
```

Output:
```
[CREATE PERSON] Starting worker...
[CREATE PERSON] Worker started. Waiting for messages on queue: hikvision_create_person...
[UPDATE KIB] Starting worker...
[UPDATE KIB] Worker started. Waiting for messages on queue: hikvision_update_kib...
[ASSIGN PRIVILEGE] Starting worker...
[ASSIGN PRIVILEGE] Worker started. Waiting for messages on queue: hikvision_assign_privilege...

============================================================
All workers started successfully!
============================================================
```

### 3. Start Publisher Worker
```bash
python worker.py
```

Output:
```
Starting worker...
Worker started. Waiting for messages on queue: hikvision_queue...
```

### 4. Start Flask App
```bash
python app.py
```

Output:
```
 * Running on http://127.0.0.1:5000
```

### 5. Trigger Processing
```bash
POST http://localhost:5000/eposh-induction
```

## Message Flow Examples

### Message 1: From Endpoint → Publisher
```json
{
  "event": "HIKVISION_SYNC",
  "data": {
    "data": [
      {
        "name": "Achmad Maulana Iriansyah A.",
        "identity_number": "3578282208990002",
        "kib_number": "2611852",
        "birth_date": {
          "ymd": "1999-08-22"
        },
        "photo": {
          "link": "https://storage.googleapis.com/eposh/public/2026/01/kib/-1767662029.png"
        },
        "regionals": [
          {
            "name": "Zona I",
            "slug": "zona-i"
          },
          {
            "name": "Zona II",
            "slug": "zona-ii"
          },
          {
            "name": "TUKS",
            "slug": "tuks"
          }
        ]
      }
    ],
    "pagination": {
      "current_page": 1,
      "last_page": 2,
      "total": 155
    }
  }
}
```

### Message 2: Publisher → CREATE_PERSON Queue
```json
{
  "employee": {
    "name": "Achmad Maulana Iriansyah A.",
    "identity_number": "3578282208990002",
    "kib_number": "2611852",
    "birth_date": {
      "ymd": "1999-08-22"
    },
    "photo": {
      "link": "https://storage.googleapis.com/eposh/public/2026/01/kib/-1767662029.png"
    },
    "regionals": [
      {
        "name": "Zona I",
        "slug": "zona-i"
      },
      {
        "name": "Zona II",
        "slug": "zona-ii"
      },
      {
        "name": "TUKS",
        "slug": "tuks"
      }
    ]
  }
}
```

### Message 3: CREATE_PERSON → UPDATE_KIB Queue
```json
{
  "personId": "18945",
  "kib_number": "2611852",
  "employee": {
    "name": "Achmad Maulana Iriansyah A.",
    "identity_number": "3578282208990002",
    "kib_number": "2611852",
    "regionals": [
      {
        "name": "Zona I",
        "slug": "zona-i"
      },
      {
        "name": "Zona II",
        "slug": "zona-ii"
      },
      {
        "name": "TUKS",
        "slug": "tuks"
      }
    ]
  }
}
```

### Message 4: UPDATE_KIB → ASSIGN_PRIVILEGE Queue
```json
{
  "personId": "18945",
  "privilege_groups": ["1", "2", "8"]
}
```

## Console Output Example

### Publisher Worker (worker.py)
```
============================================================
Received batch: Page 1/2
Publishing 100 employees to CREATE_PERSON queue...
============================================================

Published: Achmad Maulana Iriansyah A. (KIB: 2611852)
Published: Syaiful Arif (KIB: 2611854)
...

✓ Batch published: 100/100 employees sent to CREATE_PERSON queue
```

### Worker 1 - CREATE PERSON (worker_pubsub.py)
```
[CREATE PERSON] Processing: Achmad Maulana Iriansyah A.
Processing employee: Achmad Maulana Iriansyah A. (KIB: 2611852)
Mapped regionals: ['Zona I', 'Zona II', 'TUKS'] → Privilege Groups: ['1', '2', '8']
Response Status: 200
Response Body: {"code":"0","msg":"Success","data":"18945"}
✓ Employee Achmad Maulana Iriansyah A. sent successfully
[CREATE PERSON] ✓ Sent to UPDATE KIB queue: Person 18945
```

### Worker 2 - UPDATE KIB (worker_pubsub.py)
```
[UPDATE KIB] Processing: Person 18945
Text to Sign:
POST
application/json
application/json;charset=UTF-8
/artemis/api/resource/v1/person/personId/customFieldsUpdate
Generated Signature: HzgTuUzvyA0dG8BeFf/DacdtEYrMIMlujkz2c/jBR3w=
Response Status: 200
Response Body: {"code":"0","msg":"Success","data":""}
✓ Employee ID 18945 updated with KIB 2611852
[UPDATE KIB] ✓ Sent to ASSIGN PRIVILEGE queue: 3 groups
```

### Worker 3 - ASSIGN PRIVILEGE (worker_pubsub.py)
```
[ASSIGN PRIVILEGE] Processing: Person 18945
Assigning privilege groups ['1', '2', '8'] to person ID 18945
Privilege Group 1 - Status: 200
Response: {"code":"0","msg":"Success","data":""}
✓ Person 18945 added to privilege group 1
Privilege Group 2 - Status: 200
Response: {"code":"0","msg":"Success","data":""}
✓ Person 18945 added to privilege group 2
Privilege Group 8 - Status: 200
Response: {"code":"0","msg":"Success","data":""}
✓ Person 18945 added to privilege group 8
Assigned 3/3 privilege groups to person 18945
[ASSIGN PRIVILEGE] ✓ Completed for person 18945
```

## RabbitMQ Queues

| Queue Name | Purpose | Consumer |
|------------|---------|----------|
| `hikvision_queue` | Main queue from endpoint | worker.py (Publisher) |
| `hikvision_create_person` | Create person in Hikvision | worker_pubsub.py (Worker 1) |
| `hikvision_update_kib` | Update KIB custom field | worker_pubsub.py (Worker 2) |
| `hikvision_assign_privilege` | Assign privilege groups | worker_pubsub.py (Worker 3) |

## Regional to Privilege Group Mapping

| Regional (Eposh) | Slug | Privilege Group ID | HCP Name |
|------------------|------|-------------------|----------|
| Zona I | zona-i | 1 | Access Gate Zona 1 |
| Zona II | zona-ii | 2 | Access Gate Zona 2 |
| Zona III | zona-iii | 6 | Access Gate Zona 3 |
| Zona IV | zona-iv | 7 | Access Gate Zona 4 |
| TUKS | tuks | 8 | Access Gate TUKS |
| Kawasan | kawasan | 9 | Access Gate Kawasan |

## API Endpoints

### POST /eposh-induction
Fetch employees from Eposh API and publish to RabbitMQ

**Request:**
```bash
POST http://localhost:5000/eposh-induction
```

**Response:**
```json
{
  "status": "queued",
  "message": "All dates processed: 1543 employees across 17 pages sent to RabbitMQ"
}
```

### Date Range Processing
- Loop from January 1 to January 19, 2026
- Skip: January 2 and January 5
- Process: January 1, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19

## Scaling

You can run multiple instances of each worker for parallel processing:

```bash
# Terminal 1
python worker_pubsub.py

# Terminal 2
python worker_pubsub.py

# Terminal 3
python worker_pubsub.py
```

Each instance will consume from the same queues in round-robin fashion.

## Troubleshooting

### Connection Lost Error
If you see `StreamLostError`, the workers have timeout settings:
- `heartbeat=600` (10 minutes)
- `blocked_connection_timeout=300` (5 minutes)

### Queue Not Found
Make sure all queues are declared in `config.py`:
- QUEUE_CREATE_PERSON
- QUEUE_UPDATE_KIB
- QUEUE_ASSIGN_PRIVILEGE

### Messages Not Processing
Check RabbitMQ management interface:
```bash
http://localhost:15672
```
Default credentials: guest/guest
