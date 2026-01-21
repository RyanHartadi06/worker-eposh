#!/bin/bash

# Deploy Worker to Google Cloud Run
# Usage: ./deploy-gcs.sh [PROJECT_ID]

PROJECT_ID=${1:-"your-gcp-project-id"}
REGION="asia-southeast2"
SERVICE_NAME="hikvision-worker"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "==================================="
echo "Deploying Hikvision Worker to GCS"
echo "==================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Build and push Docker image
echo "Building Docker image..."
docker build -f Dockerfile.worker -t $IMAGE_NAME:latest .

echo "Pushing to Google Container Registry..."
docker push $IMAGE_NAME:latest

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME:latest \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "RABBITMQ_HOST=mq.petrokimia-gresik.com,RABBITMQ_PORT=5672,RABBITMQ_USER=user,RABBITMQ_PASSWORD=password" \
  --project $PROJECT_ID

echo ""
echo "Deployment completed!"
