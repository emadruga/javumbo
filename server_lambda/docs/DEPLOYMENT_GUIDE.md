# AWS Learner Lab Deployment Guide

**For Students & Instructors**: This guide ensures you can deploy the complete Javumbo serverless application (backend + frontend) to a fresh AWS Learner Lab without rebuilding the Lambda package.

---

## Quick Deployment (5-7 minutes)

### Prerequisites
- Active AWS Learner Lab session
- AWS CLI configured with credentials
- Node.js and npm installed
- Git clone of this repository

### Option A: Use Automated Deployment Script (Recommended)

```bash
# 1. Navigate to server_lambda directory
cd server_lambda

# 2. Download pre-built package from GitHub Releases (or shared location)
# URL will be provided by instructor
# Example:
# wget https://github.com/your-repo/javumbo/releases/download/v1.0/lambda_deployment.zip

# 3. Run the automated deployment script
./deploy.sh
```

**What the script does:**
1. Checks prerequisites (AWS CLI, Terraform, npm, credentials)
2. Verifies `lambda_deployment.zip` structure
3. Deploys infrastructure (S3 buckets, DynamoDB, Lambda, API Gateway)
4. Uploads Lambda code
5. **Automatically builds and deploys frontend** with correct API endpoint
6. Tests the deployment
7. Displays the application URL

**Time: ~5-7 minutes** (includes frontend build)

**Output**: You'll get a URL like `https://abc123.execute-api.us-east-1.amazonaws.com` - open this in your browser to use the application!

---

### Option B: Manual Deployment (Step-by-Step)

If you prefer to run commands manually:

```bash
# 1. Navigate to server_lambda directory
cd server_lambda

# 2. Download pre-built package (if needed)
# wget https://github.com/your-repo/javumbo/releases/download/v1.0/lambda_deployment.zip

# 3. Deploy infrastructure with Terraform
cd terraform
terraform init
terraform apply -auto-approve

# 4. Get outputs
API_ENDPOINT=$(terraform output -raw api_endpoint)
S3_FRONTEND_BUCKET=$(terraform output -raw s3_frontend_bucket_name)

# 5. Deploy Lambda code
cd ..
aws lambda update-function-code \
  --function-name javumbo-api \
  --zip-file fileb://lambda_deployment.zip \
  --region us-east-1

# 6. Build and deploy frontend
cd ../client_lambda

# Update frontend configuration with API endpoint
cat > .env.production <<EOF
VITE_API_BASE_URL=${API_ENDPOINT}/api
VITE_APP_BASE_PATH=/
EOF

# Install dependencies (if needed)
npm install

# Build frontend
npm run build

# Upload to S3
aws s3 sync dist/ s3://${S3_FRONTEND_BUCKET}/ --delete --region us-east-1

# 7. Test deployment
curl ${API_ENDPOINT}/api/health
# Expected: {"msg":"Missing Authorization Header"}

# 8. Open in browser
echo "Application URL: ${API_ENDPOINT}"
```

**Time: ~5-7 minutes** (after Terraform apply completes)

---

## Option C: Rebuild Package (If package is unavailable)

### Prerequisites
- Docker Desktop running
- All source code in `server_lambda/src/`

### Steps

```bash
cd server_lambda

# 1. Clean old artifacts
rm -rf package lambda_deployment.zip

# 2. Install dependencies using Docker (Linux binaries)
docker run --rm --platform linux/amd64 \
  --entrypoint pip \
  -v "$(pwd)":/var/task \
  public.ecr.aws/lambda/python:3.11 \
  install -r /var/task/requirements.txt -t /var/task/package/ --upgrade

# 3. Package dependencies
cd package
zip -r ../lambda_deployment.zip . -x "*.pyc" -x "*__pycache__*"

# 4. Add application code at root level
cd ../src
zip -g ../lambda_deployment.zip *.py

# 5. Verify package structure
cd ..
unzip -l lambda_deployment.zip | grep -E "(app\.py|lambda_handler\.py|bcrypt)"

# Expected output:
# ✅ app.py at root level
# ✅ lambda_handler.py at root level
# ✅ bcrypt/_bcrypt.abi3.so (Linux binary, ~631KB)

# 6. Deploy infrastructure
cd terraform
terraform init
terraform apply -auto-approve

# 7. Deploy Lambda code
aws lambda update-function-code \
  --function-name javumbo-api \
  --zip-file fileb://../lambda_deployment.zip \
  --region us-east-1
```

**Time: ~15 minutes** (including Docker build)

---

## Preserving Deployment Artifacts Between Labs

### Before Lab Expires: Save These

#### 1. **Lambda Deployment Package** (CRITICAL)
```bash
# Copy to a permanent location
cp server_lambda/lambda_deployment.zip ~/javumbo_backups/lambda_deployment_$(date +%Y%m%d).zip
```

**Where to Store**:
- ✅ **GitHub Repository** (recommended if <100MB or using Git LFS)
- ✅ **Google Drive / Dropbox** (share with students)
- ✅ **Personal S3 bucket** (outside Learner Lab)
- ✅ **GitHub Releases** (public or private)

#### 2. **Terraform State** (Optional, for reference)
```bash
# This is less critical since infrastructure is disposable
cd server_lambda/terraform
cp terraform.tfstate ~/javumbo_backups/terraform_state_$(date +%Y%m%d).tfstate
```

#### 3. **User Data** (If needed for demos)
Export sample user databases before lab expires:

```bash
# Download sample user databases from S3
aws s3 cp s3://javumbo-user-dbs-YOUR-ACCOUNT-ID/user_dbs/testuser2025.anki2 \
  ~/javumbo_backups/sample_user_db.anki2

# Download DynamoDB user table (optional)
aws dynamodb scan --table-name javumbo-users > ~/javumbo_backups/users_backup.json
```

---

## For Instructors: Distributing the Package

### Option 1: GitHub Releases (Recommended)

```bash
# 1. Create a GitHub release
# 2. Upload lambda_deployment.zip as a release asset
# 3. Students download it with:

wget https://github.com/emadruga/javumbo/releases/download/v1.0/lambda_deployment.zip
```

### Option 2: Google Drive / Shared Folder

1. Upload `lambda_deployment.zip` to shared folder
2. Generate shareable link
3. Students download:
   ```bash
   # Google Drive direct download
   curl -L "YOUR_SHARE_LINK" -o lambda_deployment.zip
   ```

### Option 3: Git LFS (For repositories)

```bash
# One-time setup in repository
git lfs install
git lfs track "*.zip"
git add .gitattributes server_lambda/lambda_deployment.zip
git commit -m "Add pre-built Lambda package"
git push
```

Students clone with LFS:
```bash
git lfs clone https://github.com/emadruga/javumbo.git
```

---

## Automated Deployment Script for Students

Create `server_lambda/deploy.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Javumbo Serverless Deployment Script"
echo "========================================"

# Check prerequisites
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI not installed"; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo "❌ Terraform not installed"; exit 1; }

# Check if package exists
if [ ! -f "lambda_deployment.zip" ]; then
    echo "❌ lambda_deployment.zip not found!"
    echo "Please download it from: [INSTRUCTOR_LINK]"
    exit 1
fi

# Verify package structure
echo "✅ Verifying package structure..."
unzip -l lambda_deployment.zip | grep -q "app.py" || { echo "❌ Invalid package"; exit 1; }

# Deploy infrastructure
echo "📦 Deploying infrastructure with Terraform..."
cd terraform
terraform init
terraform apply -auto-approve

# Get API Gateway endpoint
API_ENDPOINT=$(terraform output -raw api_endpoint)

# Deploy Lambda code
echo "🔧 Deploying Lambda function code..."
aws lambda update-function-code \
  --function-name javumbo-api \
  --zip-file fileb://../lambda_deployment.zip \
  --region us-east-1 \
  --query '{FunctionName: FunctionName, LastModified: LastModified, CodeSize: CodeSize}' \
  --output table

# Wait for deployment
echo "⏳ Waiting for deployment to propagate..."
sleep 10

# Test deployment
echo "🧪 Testing deployment..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${API_ENDPOINT}/api/health")

if [ "$HTTP_CODE" -eq 401 ]; then
    echo "✅ Deployment successful!"
    echo ""
    echo "🎉 Your API is live at:"
    echo "   ${API_ENDPOINT}"
    echo ""
    echo "📖 Test it with:"
    echo "   curl ${API_ENDPOINT}/api/health"
    echo ""
    echo "🔐 Register a user:"
    echo '   curl -X POST '${API_ENDPOINT}'/api/register \'
    echo '     -H "Content-Type: application/json" \'
    echo '     -d '"'"'{"username":"student1","name":"Student One","password":"password123456"}'"'"
else
    echo "❌ Deployment verification failed (HTTP $HTTP_CODE)"
    echo "Check CloudWatch logs:"
    echo "   aws logs tail /aws/lambda/javumbo-api --since 5m --follow"
fi
```

Make it executable:
```bash
chmod +x server_lambda/deploy.sh
```

---

## Troubleshooting

### Issue: "Unable to import module 'lambda_handler'"

**Cause**: Wrong package deployed (macOS binaries instead of Linux)

**Fix**: Rebuild package using Docker (see Option B above)

### Issue: "Endpoint not found" (404)

**Cause**: Old package with wrong routes

**Fix**: Redeploy the latest package:
```bash
aws lambda update-function-code \
  --function-name javumbo-api \
  --zip-file fileb://lambda_deployment.zip \
  --region us-east-1
```

### Issue: "Internal Server Error" (500)

**Check logs**:
```bash
aws logs tail /aws/lambda/javumbo-api --since 10m --follow
```

Common causes:
- Missing environment variables (set in terraform/lambda.tf)
- S3 bucket permissions
- DynamoDB table not created

---

## Cost Considerations

**AWS Learner Lab Restrictions**:
- Limited budget (~$50-100 credits)
- Services auto-shutdown after session ends
- No persistent storage outside S3

**Javumbo Serverless Costs** (estimated):
- Lambda: ~$0.20/month (low usage)
- S3: ~$0.50/month (storage)
- DynamoDB: Free tier eligible
- API Gateway: ~$0.10/month

**Total: <$1/month for low-traffic testing**

---

## Best Practices for Learner Labs

1. **Deploy Early**: Start deployment immediately after starting lab session
2. **Export Data Frequently**: Download user databases before session ends
3. **Use terraform destroy**: Clean up resources to avoid budget issues
4. **Share Artifacts**: Keep lambda_deployment.zip in shared location
5. **Document Custom Changes**: If students modify code, rebuild package before lab expires

---

## Summary: Instructor Workflow

**Before First Lab**:
1. Build `lambda_deployment.zip` using Docker
2. Upload to GitHub Releases or shared folder
3. Create `deploy.sh` automation script
4. Test deployment in fresh Learner Lab

**For Each Lab Session**:
1. Students clone repository
2. Students download `lambda_deployment.zip`
3. Students run `./deploy.sh`
4. Deployment completes in ~5 minutes

**After Lab Expires**:
- Students run `terraform destroy` (optional, lab auto-cleans)
- Artifacts (lambda_deployment.zip) remain in Git/shared storage
- Next lab session repeats the process

---

## Questions?

Contact: [Your Email/Slack]

Last Updated: 2025-12-17
Package Version: v1.0 (Compatible with Python 3.11, AWS Lambda)
