# Deploy Hikvision Worker ke Google Cloud

## Prerequisites
1. Install Google Cloud SDK
2. Login ke GCP: `gcloud auth login`
3. Configure Docker untuk GCR: `gcloud auth configure-docker`
4. Set project: `gcloud config set project YOUR_PROJECT_ID`

## Konfigurasi RabbitMQ Eksternal
Worker ini sudah dikonfigurasi untuk menggunakan RabbitMQ eksternal di:
- **Host**: mq.petrokimia-gresik.com
- **Port**: 5672
- **Username**: user
- **Password**: password

## Cara Deploy

### Option 1: Manual Deploy
```bash
# Build image
docker build -f Dockerfile.worker -t gcr.io/YOUR_PROJECT_ID/hikvision-worker:latest .

# Push ke Google Container Registry
docker push gcr.io/YOUR_PROJECT_ID/hikvision-worker:latest

# Deploy ke Cloud Run
gcloud run deploy hikvision-worker \
  --image gcr.io/YOUR_PROJECT_ID/hikvision-worker:latest \
  --region asia-southeast2 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "RABBITMQ_HOST=mq.petrokimia-gresik.com,RABBITMQ_PORT=5672,RABBITMQ_USER=user,RABBITMQ_PASSWORD=password"
```

### Option 2: Menggunakan Script

**Linux/Mac:**
```bash
chmod +x deploy-gcs.sh
./deploy-gcs.sh YOUR_PROJECT_ID
```

**Windows:**
```batch
deploy-gcs.bat YOUR_PROJECT_ID
```

### Option 3: Google Cloud Build (CI/CD)
```bash
gcloud builds submit --config cloudbuild.yaml
```

## Monitoring

Setelah deploy, Anda bisa:
- Lihat logs: `gcloud run logs read hikvision-worker --region asia-southeast2`
- Lihat service: `gcloud run services list --region asia-southeast2`
- Describe service: `gcloud run services describe hikvision-worker --region asia-southeast2`

## Update Konfigurasi

Jika perlu update environment variables:
```bash
gcloud run services update hikvision-worker \
  --region asia-southeast2 \
  --set-env-vars "RABBITMQ_HOST=mq.petrokimia-gresik.com,RABBITMQ_PORT=5672"
```

## Troubleshooting

### Cek logs worker
```bash
gcloud run logs read hikvision-worker --region asia-southeast2 --limit 50
```

### Test koneksi RabbitMQ
Worker akan otomatis mencoba koneksi ke RabbitMQ saat start. Cek logs untuk memastikan koneksi berhasil.

## File Penting
- `Dockerfile.worker` - Docker image untuk worker
- `cloudbuild.yaml` - Konfigurasi Google Cloud Build
- `.env.production` - Environment variables untuk production
- `deploy-gcs.sh` / `deploy-gcs.bat` - Script deployment
