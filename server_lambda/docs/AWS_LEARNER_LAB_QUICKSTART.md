# Javumbo Serverless - Quick Start Guide

**For AWS Learner Lab Students**: Deploy the complete serverless application (backend + frontend) in 5 minutes.

---

## Prerequisites Checklist

- [ ] Active AWS Learner Lab session
- [ ] AWS CLI installed
- [ ] AWS credentials configured (`aws configure`)
- [ ] Node.js and npm installed (for frontend build)
- [ ] Git repository cloned
- [ ] Pre-built `lambda_deployment.zip` downloaded

---

## Step 1: Download Deployment Package

**Option A: From GitHub Releases** (recommended)
```bash
cd server_lambda
wget https://github.com/emadruga/javumbo/releases/download/v1.0/lambda_deployment.zip
```

**Option B: From instructor-provided link**
```bash
# Your instructor will provide the download URL
curl -L "INSTRUCTOR_DOWNLOAD_LINK" -o lambda_deployment.zip
```

**Option C: Build it yourself** (if unavailable)
```bash
./build_lambda_package.sh
```

---

## Step 2: Deploy Everything

```bash
./deploy.sh
```

**What this does:**
1. Checks prerequisites (AWS CLI, Terraform, credentials, npm)
2. Verifies `lambda_deployment.zip` structure
3. Deploys infrastructure with Terraform (S3 buckets, DynamoDB, Lambda, API Gateway)
4. Uploads Lambda code
5. **Builds and deploys frontend** to S3 (with dynamic API endpoint)
6. Tests the deployment

**Time: ~5-7 minutes** (includes frontend build)

**Important**: The script automatically:
- Detects the API Gateway endpoint URL
- Updates the frontend configuration to use this URL
- Builds the frontend with the correct API endpoint
- Uploads the frontend to the S3 bucket

This ensures your frontend always points to the correct API, even in ephemeral AWS Learner Lab environments.

---

## Step 3: Test Your Deployment

### Access the Web Application

The easiest way to test is to open the web application in your browser:

```bash
# The deploy script outputs the URL - it looks like:
# https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com
```

**In your browser:**
1. Navigate to the API endpoint URL (shown in deploy output)
2. Click "Register" and create a new user
3. Login with your credentials
4. Start using the flashcard application!

### Or Test the API Directly

```bash
# Replace with your API endpoint from deploy.sh output
API_ENDPOINT="https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com"

# Health Check
curl $API_ENDPOINT/api/health
# Expected: {"msg":"Missing Authorization Header"}

# Register a User
curl -X POST $API_ENDPOINT/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"student1","name":"Student One","password":"password123456"}'
# Expected: {"message":"User registered successfully"}

# Login
curl -X POST $API_ENDPOINT/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"student1","password":"password123456"}'
# Expected: {"access_token":"eyJ...", "username":"student1", "name":"Student One"}

# Get Decks (Authenticated)
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
curl -X GET $API_ENDPOINT/api/decks \
  -H "Authorization: Bearer $TOKEN"
# Expected: {"decks":[...], "session_id":"sess_..."}
```

---

## Common Issues

### "lambda_deployment.zip not found"
**Fix**: Download the package (see Step 1)

### "AWS credentials not configured"
**Fix**: Run `aws configure` and enter your Learner Lab credentials

### "npm is not installed"
**Fix**: Install Node.js and npm from https://nodejs.org/
- The deploy script needs npm to build the frontend

### "Terraform not found"
**Fix**: Install Terraform from https://www.terraform.io/downloads

### Deployment verification failed (HTTP 500)
**Check logs**:
```bash
aws logs tail /aws/lambda/javumbo-api --since 5m --follow
```

### Frontend shows "Network Error" or can't connect to API
**This shouldn't happen** - the deploy script automatically configures the frontend with the correct API endpoint. If it does:
1. Check that the deploy script completed successfully
2. Verify the API endpoint is working: `curl $API_ENDPOINT/api/health`
3. Check browser console for errors (F12)

---

## Clean Up (End of Session)

**Destroy all resources** to avoid budget issues:
```bash
cd terraform
terraform destroy
```

**WARNING**: This deletes all user data!

---

## Next Steps

- **API Documentation**: See `docs/REST_API.md`
- **Full Deployment Guide**: See `docs/DEPLOYMENT_GUIDE.md`
- **Architecture Details**: See `docs/REFACTOR_WEEK_4.md`

---

## Support

- **Instructor**: [Contact info]
- **Issues**: GitHub Issues
- **Documentation**: `server_lambda/docs/`

---

**Time to complete**: ~10 minutes (including testing)
**Cost**: <$0.01 per deployment test
