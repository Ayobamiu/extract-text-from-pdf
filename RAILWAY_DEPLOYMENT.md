# Flask PDF Service - Railway Deployment Guide

## 🚀 **Deployment Steps**

### **Step 1: Create Railway Service**

1. **Go to Railway Dashboard**: https://railway.app/dashboard
2. **Select your project**: "truthful-recreation"
3. **Click "New Service"**
4. **Choose "GitHub Repo"** or **"Empty Service"**
5. **Name it**: `flask-pdf-service`

### **Step 2: Configure Environment Variables**

Set these environment variables in Railway:

#### **Required Variables**

```
GOOGLE_PROJECT_ID=your-google-cloud-project-id
GOOGLE_PROCESSOR_ID=your-document-ai-processor-id
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"your-project-id",...}
```

#### **Optional Variables**

```
GOOGLE_LOCATION=us
HOST=0.0.0.0
PORT=5001
DEBUG=false
MAX_PAGES_PER_REQUEST=15
MAX_FILE_SIZE=52428800
UPLOAD_FOLDER=/tmp/uploads
TEMP_FOLDER=/tmp/temp
ENABLE_TABLE_EXTRACTION=true
ENABLE_OCR_EXTRACTION=true
LOG_LEVEL=INFO
```

### **Step 3: Get Google Service Account JSON**

1. **Go to Google Cloud Console**: https://console.cloud.google.com/
2. **Navigate to**: IAM & Admin > Service Accounts
3. **Create or select a service account**
4. **Generate a new JSON key**
5. **Copy the entire JSON content**
6. **Paste it as `GOOGLE_SERVICE_ACCOUNT_JSON`** in Railway

### **Step 4: Deploy**

1. **Connect your GitHub repo** or **upload files**
2. **Railway will automatically detect Python** and install dependencies
3. **The service will start** using the Procfile

### **Step 5: Update Node.js Service**

After Flask is deployed, update your Node.js service's `FLASK_URL`:

```
FLASK_URL=https://flask-pdf-service-production.up.railway.app
```

## 🔧 **Google Credentials Options**

### **Option 1: Service Account JSON (Recommended)**

- Store the entire JSON as `GOOGLE_SERVICE_ACCOUNT_JSON`
- The app creates a temporary file at runtime
- Most secure and Railway-compatible

### **Option 2: Individual Environment Variables**

- Set each credential field separately
- Requires code changes to use individual variables
- Less secure but more granular

## 📋 **Testing**

After deployment, test the service:

```bash
# Health check
curl https://your-flask-service.up.railway.app/health

# Test extraction
curl -X POST -F "file=@test.pdf" https://your-flask-service.up.railway.app/extract
```

## 🚨 **Troubleshooting**

### **Common Issues**

1. **Google Credentials Error**

   - Check `GOOGLE_SERVICE_ACCOUNT_JSON` is valid JSON
   - Verify service account has Document AI permissions

2. **Port Issues**

   - Railway sets `PORT` automatically
   - Don't hardcode port numbers

3. **File Upload Issues**

   - Check `MAX_FILE_SIZE` setting
   - Ensure temp directories are writable

4. **Memory Issues**
   - Large PDFs may need more memory
   - Consider upgrading Railway plan

## 📊 **Monitoring**

- **Health Check**: `/health`
- **Logs**: Available in Railway dashboard
- **Metrics**: CPU, Memory, Network usage

## 🔄 **Updates**

To update the service:

1. **Push changes to GitHub** (if using GitHub integration)
2. **Or redeploy** from Railway dashboard
3. **Environment variables** persist across deployments
