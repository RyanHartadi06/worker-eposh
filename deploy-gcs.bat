@echo off
REM Deploy Worker to Google Cloud Run (Windows)
REM Usage: deploy-gcs.bat [PROJECT_ID]

SET PROJECT_ID=%1
IF "%PROJECT_ID%"=="" SET PROJECT_ID=your-gcp-project-id

SET REGION=asia-southeast2
SET SERVICE_NAME=hikvision-worker
SET IMAGE_NAME=gcr.io/%PROJECT_ID%/%SERVICE_NAME%

echo ===================================
echo Deploying Hikvision Worker to GCS
echo ===================================
echo Project: %PROJECT_ID%
echo Region: %REGION%
echo Service: %SERVICE_NAME%
echo.

REM Build and push Docker image
echo Building Docker image...
docker build -f Dockerfile.worker -t %IMAGE_NAME%:latest .

echo Pushing to Google Container Registry...
docker push %IMAGE_NAME%:latest

REM Deploy to Cloud Run
echo Deploying to Cloud Run...
gcloud run deploy %SERVICE_NAME% ^
  --image %IMAGE_NAME%:latest ^
  --region %REGION% ^
  --platform managed ^
  --allow-unauthenticated ^
  --set-env-vars "RABBITMQ_HOST=mq.petrokimia-gresik.com,RABBITMQ_PORT=5672,RABBITMQ_USER=user,RABBITMQ_PASSWORD=password" ^
  --project %PROJECT_ID%

echo.
echo Deployment completed!
