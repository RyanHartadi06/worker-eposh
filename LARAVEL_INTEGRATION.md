# Laravel Integration with Hikvision Worker

## Installation

### 1. Install RabbitMQ Package for Laravel

```bash
composer require php-amqplib/php-amqplib
```

### 2. Create RabbitMQ Service

**File: `app/Services/RabbitMQService.php`**

```php
<?php

namespace App\Services;

use PhpAmqpLib\Connection\AMQPStreamConnection;
use PhpAmqpLib\Message\AMQPMessage;
use Exception;

class RabbitMQService
{
    private $connection;
    private $channel;

    public function __construct()
    {
        $this->connection = new AMQPStreamConnection(
            env('RABBITMQ_HOST', 'localhost'),
            env('RABBITMQ_PORT', 5672),
            env('RABBITMQ_USER', 'guest'),
            env('RABBITMQ_PASSWORD', 'guest')
        );
        $this->channel = $this->connection->channel();
    }

    /**
     * Publish message to queue
     */
    public function publish($queueName, $message)
    {
        // Declare queue (ensure it exists)
        $this->channel->queue_declare(
            $queueName,     // queue name
            false,          // passive
            true,           // durable
            false,          // exclusive
            false           // auto_delete
        );

        // Create message
        $msg = new AMQPMessage(
            json_encode($message),
            ['delivery_mode' => AMQPMessage::DELIVERY_MODE_PERSISTENT]
        );

        // Publish to queue
        $this->channel->basic_publish($msg, '', $queueName);

        \Log::info("Published to queue: {$queueName}", ['message' => $message]);

        return true;
    }

    public function __destruct()
    {
        $this->channel->close();
        $this->connection->close();
    }
}
```

### 3. Configure Environment Variables

**File: `.env`**

```env
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

# Eposh API
EPOSH_API_URL=https://gcp-api.eposh.id/v1/induction/employees
EPOSH_API_KEY=4237aa07-376f-4db9-9c83-9cf91dc6438f
EPOSH_APP_ID=hcpvision
```

## Implementation Examples

### Option 1: Direct to Main Queue (Simple)

**File: `app/Http/Controllers/HikvisionSyncController.php`**

```php
<?php

namespace App\Http\Controllers;

use App\Services\RabbitMQService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;

class HikvisionSyncController extends Controller
{
    private $rabbitmq;

    public function __construct(RabbitMQService $rabbitmq)
    {
        $this->rabbitmq = $rabbitmq;
    }

    /**
     * Sync employees from Eposh to Hikvision via RabbitMQ
     */
    public function syncEmployees(Request $request)
    {
        try {
            $baseUrl = env('EPOSH_API_URL');
            $headers = [
                'x-api-key' => env('EPOSH_API_KEY'),
                'x-app-id' => env('EPOSH_APP_ID'),
            ];

            // Skip dates
            $skipDates = [2, 5];
            $totalEmployees = 0;
            $totalPages = 0;

            // Loop through dates
            for ($day = 1; $day <= 19; $day++) {
                if (in_array($day, $skipDates)) {
                    \Log::info("Skipping January {$day}, 2026");
                    continue;
                }

                $inductionDate = sprintf('2026-01-%02d', $day);
                \Log::info("Processing induction date: {$inductionDate}");

                // Fetch first page
                $params = [
                    'induction_date' => $inductionDate,
                    'include_base64' => 'false',
                    'page' => 1,
                    'limit' => 100,
                ];

                $response = Http::withHeaders($headers)
                    ->withOptions(['verify' => false])
                    ->get($baseUrl, $params);

                if (!$response->successful()) {
                    \Log::error("Failed to fetch employees for {$inductionDate}");
                    continue;
                }

                $firstPage = $response->json();
                $pagination = $firstPage['pagination'] ?? [];
                $totalPagesForDate = $pagination['last_page'] ?? 1;
                $totalRecords = $pagination['total'] ?? 0;

                if ($totalRecords == 0) {
                    \Log::info("No employees found for {$inductionDate}");
                    continue;
                }

                \Log::info("Found {$totalRecords} employees across {$totalPagesForDate} pages for {$inductionDate}");

                // Send first page to RabbitMQ
                $this->rabbitmq->publish('hikvision_queue', [
                    'event' => 'HIKVISION_SYNC',
                    'data' => $firstPage,
                ]);

                $totalEmployees += count($firstPage['data'] ?? []);
                $totalPages++;

                // Send remaining pages
                for ($page = 2; $page <= $totalPagesForDate; $page++) {
                    $params['page'] = $page;
                    $pageResponse = Http::withHeaders($headers)
                        ->withOptions(['verify' => false])
                        ->get($baseUrl, $params);

                    if ($pageResponse->successful()) {
                        $pageData = $pageResponse->json();
                        $this->rabbitmq->publish('hikvision_queue', [
                            'event' => 'HIKVISION_SYNC',
                            'data' => $pageData,
                        ]);

                        $totalEmployees += count($pageData['data'] ?? []);
                        $totalPages++;
                        \Log::info("Page {$page}/{$totalPagesForDate} queued for {$inductionDate}");
                    }
                }

                \Log::info("Completed {$inductionDate}: {$totalRecords} employees queued");
            }

            return response()->json([
                'status' => 'queued',
                'message' => "All dates processed: {$totalEmployees} employees across {$totalPages} pages sent to RabbitMQ",
            ]);

        } catch (\Exception $e) {
            \Log::error("Error in syncEmployees: " . $e->getMessage());
            return response()->json([
                'status' => 'error',
                'message' => $e->getMessage(),
            ], 500);
        }
    }
}
```

### Option 2: Direct to CREATE_PERSON Queue (Advanced Pub/Sub)

**File: `app/Http/Controllers/HikvisionSyncController.php`**

```php
<?php

namespace App\Http\Controllers;

use App\Services\RabbitMQService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;

class HikvisionSyncController extends Controller
{
    private $rabbitmq;

    public function __construct(RabbitMQService $rabbitmq)
    {
        $this->rabbitmq = $rabbitmq;
    }

    /**
     * Sync employees directly to CREATE_PERSON queue (Pub/Sub mode)
     */
    public function syncEmployeesPubSub(Request $request)
    {
        try {
            $baseUrl = env('EPOSH_API_URL');
            $headers = [
                'x-api-key' => env('EPOSH_API_KEY'),
                'x-app-id' => env('EPOSH_APP_ID'),
            ];

            $skipDates = [2, 5];
            $totalEmployees = 0;

            for ($day = 1; $day <= 19; $day++) {
                if (in_array($day, $skipDates)) continue;

                $inductionDate = sprintf('2026-01-%02d', $day);
                $params = [
                    'induction_date' => $inductionDate,
                    'include_base64' => 'false',
                    'page' => 1,
                    'limit' => 100,
                ];

                $response = Http::withHeaders($headers)
                    ->withOptions(['verify' => false])
                    ->get($baseUrl, $params);

                if (!$response->successful()) continue;

                $firstPage = $response->json();
                $pagination = $firstPage['pagination'] ?? [];
                $totalPagesForDate = $pagination['last_page'] ?? 1;
                $employees = $firstPage['data'] ?? [];

                // Publish each employee to CREATE_PERSON queue
                foreach ($employees as $employee) {
                    $this->rabbitmq->publish('hikvision_create_person', [
                        'employee' => $employee,
                    ]);
                    $totalEmployees++;
                }

                // Process remaining pages
                for ($page = 2; $page <= $totalPagesForDate; $page++) {
                    $params['page'] = $page;
                    $pageResponse = Http::withHeaders($headers)
                        ->withOptions(['verify' => false])
                        ->get($baseUrl, $params);

                    if ($pageResponse->successful()) {
                        $pageData = $pageResponse->json();
                        $pageEmployees = $pageData['data'] ?? [];

                        foreach ($pageEmployees as $employee) {
                            $this->rabbitmq->publish('hikvision_create_person', [
                                'employee' => $employee,
                            ]);
                            $totalEmployees++;
                        }
                    }
                }
            }

            return response()->json([
                'status' => 'queued',
                'message' => "{$totalEmployees} employees sent directly to CREATE_PERSON queue",
            ]);

        } catch (\Exception $e) {
            \Log::error("Error in syncEmployeesPubSub: " . $e->getMessage());
            return response()->json([
                'status' => 'error',
                'message' => $e->getMessage(),
            ], 500);
        }
    }
}
```

### Option 3: Publish Single Employee

**File: `app/Http/Controllers/HikvisionSyncController.php`**

```php
/**
 * Sync single employee to Hikvision
 */
public function syncSingleEmployee(Request $request)
{
    $validated = $request->validate([
        'name' => 'required|string',
        'identity_number' => 'required|string',
        'kib_number' => 'required|string',
        'birth_date' => 'required|array',
        'photo' => 'nullable|array',
        'regionals' => 'required|array',
    ]);

    try {
        // Publish to CREATE_PERSON queue
        $this->rabbitmq->publish('hikvision_create_person', [
            'employee' => $validated,
        ]);

        return response()->json([
            'status' => 'queued',
            'message' => "Employee {$validated['name']} sent to processing queue",
        ]);

    } catch (\Exception $e) {
        return response()->json([
            'status' => 'error',
            'message' => $e->getMessage(),
        ], 500);
    }
}
```

## Routes

**File: `routes/api.php`**

```php
use App\Http\Controllers\HikvisionSyncController;

Route::prefix('hikvision')->group(function () {
    // Option 1: Via main queue (worker.py processes)
    Route::post('/sync', [HikvisionSyncController::class, 'syncEmployees']);
    
    // Option 2: Direct to pub/sub (worker_pubsub.py processes)
    Route::post('/sync-pubsub', [HikvisionSyncController::class, 'syncEmployeesPubSub']);
    
    // Option 3: Single employee
    Route::post('/sync-single', [HikvisionSyncController::class, 'syncSingleEmployee']);
});
```

## Testing

### Test with Postman/cURL

**Sync All Employees (Main Queue):**
```bash
curl -X POST http://localhost:8000/api/hikvision/sync
```

**Sync All Employees (Pub/Sub):**
```bash
curl -X POST http://localhost:8000/api/hikvision/sync-pubsub
```

**Sync Single Employee:**
```bash
curl -X POST http://localhost:8000/api/hikvision/sync-single \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "identity_number": "1234567890123456",
    "kib_number": "2611999",
    "birth_date": {
      "ymd": "1990-01-01"
    },
    "photo": {
      "link": "https://example.com/photo.jpg"
    },
    "regionals": [
      {
        "name": "Zona I",
        "slug": "zona-i"
      }
    ]
  }'
```

## Message Format Examples

### Message to Main Queue (hikvision_queue)

```json
{
  "event": "HIKVISION_SYNC",
  "data": {
    "data": [
      {
        "name": "John Doe",
        "identity_number": "1234567890123456",
        "kib_number": "2611999",
        "birth_date": {
          "ymd": "1990-01-01"
        },
        "photo": {
          "link": "https://example.com/photo.jpg"
        },
        "regionals": [
          {
            "name": "Zona I",
            "slug": "zona-i"
          }
        ]
      }
    ],
    "pagination": {
      "current_page": 1,
      "last_page": 1,
      "total": 1
    }
  }
}
```

### Message to CREATE_PERSON Queue (hikvision_create_person)

```json
{
  "employee": {
    "name": "John Doe",
    "identity_number": "1234567890123456",
    "kib_number": "2611999",
    "birth_date": {
      "ymd": "1990-01-01"
    },
    "photo": {
      "link": "https://example.com/photo.jpg"
    },
    "regionals": [
      {
        "name": "Zona I",
        "slug": "zona-i"
      }
    ]
  }
}
```

## Architecture Comparison

### Architecture 1: Via Main Queue

```
Laravel → RabbitMQ (hikvision_queue) → worker.py → CREATE_PERSON queue → worker_pubsub.py
```

**Pros:**
- Simple integration
- worker.py handles pagination & splitting

**Cons:**
- Extra processing step

### Architecture 2: Direct Pub/Sub

```
Laravel → RabbitMQ (hikvision_create_person) → worker_pubsub.py
```

**Pros:**
- Direct to processing
- Faster processing
- Laravel handles pagination & splitting

**Cons:**
- More logic in Laravel

## Monitoring

### Check Queue Status from Laravel

```php
use PhpAmqpLib\Connection\AMQPStreamConnection;

public function queueStatus()
{
    $connection = new AMQPStreamConnection(
        env('RABBITMQ_HOST'),
        env('RABBITMQ_PORT'),
        env('RABBITMQ_USER'),
        env('RABBITMQ_PASSWORD')
    );
    
    $channel = $connection->channel();
    
    $queues = [
        'hikvision_queue',
        'hikvision_create_person',
        'hikvision_update_kib',
        'hikvision_assign_privilege',
    ];
    
    $status = [];
    foreach ($queues as $queue) {
        list($queueName, $messageCount, $consumerCount) = $channel->queue_declare($queue, true);
        $status[$queue] = [
            'messages' => $messageCount,
            'consumers' => $consumerCount,
        ];
    }
    
    $channel->close();
    $connection->close();
    
    return response()->json($status);
}
```

**Route:**
```php
Route::get('/hikvision/queue-status', [HikvisionSyncController::class, 'queueStatus']);
```

## Error Handling

```php
try {
    $this->rabbitmq->publish('hikvision_create_person', [
        'employee' => $employee,
    ]);
    
    \Log::info("Employee queued successfully", ['employee' => $employee['name']]);
    
} catch (\PhpAmqpLib\Exception\AMQPConnectionClosedException $e) {
    \Log::error("RabbitMQ connection closed: " . $e->getMessage());
    return response()->json(['error' => 'Queue service unavailable'], 503);
    
} catch (\Exception $e) {
    \Log::error("Failed to queue employee: " . $e->getMessage());
    return response()->json(['error' => 'Failed to queue employee'], 500);
}
```

## Best Practices

1. **Use Queue Jobs** (Optional - for better Laravel integration):
```php
php artisan make:job PublishToHikvision

// app/Jobs/PublishToHikvision.php
class PublishToHikvision implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public function handle(RabbitMQService $rabbitmq)
    {
        $rabbitmq->publish('hikvision_create_person', $this->employee);
    }
}

// Usage
PublishToHikvision::dispatch($employee);
```

2. **Add Rate Limiting** to prevent overwhelming the API
3. **Log all operations** for debugging
4. **Use transactions** when dealing with database operations
5. **Handle errors gracefully** and retry failed messages

## Recommended: Use Laravel Queue + RabbitMQ

For better Laravel integration, use Laravel's built-in queue system with RabbitMQ driver:

```bash
composer require vladimir-yuldashev/laravel-queue-rabbitmq
```

This provides native Laravel queue features with RabbitMQ backend.
