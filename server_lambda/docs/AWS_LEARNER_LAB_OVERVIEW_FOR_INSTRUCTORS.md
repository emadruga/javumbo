# AWS Learner Lab - Complete Overview for Instructors

**Purpose**: This document provides instructors with a complete overview of the AWS Learner Lab deployment strategy for the Javumbo serverless application (backend + frontend).

---

## The Challenge

AWS Academy Learner Labs are ephemeral:
- Labs auto-terminate after each session
- Students get fresh AWS accounts each time
- All AWS resources are deleted between sessions
- **Building Lambda packages from scratch takes 15-20 minutes**
- **API Gateway URLs change with each deployment**

## The Solution

**Save the pre-built Lambda deployment package once, reuse it forever.**
**Automated script handles dynamic API Gateway URLs for frontend configuration.**

Students deploy the complete application (backend + frontend) in **5-7 minutes** instead of 15-20 minutes by:
1. Downloading a pre-built package instead of rebuilding it
2. Running an automated script that configures the frontend with the correct API endpoint

---

## Files Created for This Solution

### **Automation Scripts** (in `server_lambda/`)

| File | Size | Purpose |
|------|------|---------|
| **`deploy.sh`** | ~8 KB | Students run this to deploy everything (checks prerequisites, deploys infrastructure, uploads Lambda code, **builds and deploys frontend with correct API URL**, tests deployment) |
| **`build_lambda_package.sh`** | 4.2 KB | Instructor runs this once to create `lambda_deployment.zip` with Linux binaries |

### **Documentation** (in `server_lambda/docs/`)

| File | Size | Audience | Purpose |
|------|------|----------|---------|
| **`AWS_LEARNER_LAB_OVERVIEW_FOR_INSTRUCTORS.md`** | This file | Instructors | Complete overview and quick reference |
| **`AWS_LEARNER_LAB_ARTIFACT_PRESERVATION.md`** | 9.4 KB | Instructors | Detailed guide on preserving artifacts, storage options, workflow |
| **`DEPLOYMENT_GUIDE.md`** | 8.7 KB | Students & Instructors | Complete deployment procedures, troubleshooting |
| **`AWS_LEARNER_LAB_QUICKSTART.md`** | 3.1 KB | Students | Quick 3-step deployment guide |

---

## The Critical Artifact: `lambda_deployment.zip`

**What it contains:**
- All Python dependencies (Flask, boto3, bcrypt, etc.)
- **Linux x86_64 binaries** (essential for AWS Lambda)
- Your application code (`app.py`, `lambda_handler.py`, etc.)

**Size:** ~16-17 MB

**Why it's critical:**
- Takes 10-15 minutes to build with Docker
- Must use Linux binaries (macOS binaries cause "invalid ELF header" errors)
- Students cannot build it without Docker Desktop

**This is the ONLY file you need to preserve between lab sessions.**

---

## Quick Answer: What to Do Before Lab Expires

### Minimum Required (Takes 30 seconds)

```bash
# Save the package locally
cp server_lambda/lambda_deployment.zip \
   ~/javumbo_backups/lambda_deployment_$(date +%Y%m%d).zip
```

### Recommended for Teaching (One-time setup)

**Upload to GitHub Releases** (free, unlimited bandwidth, easy for students):

```bash
# 1. Create git tag
git tag -a v1.0 -m "Lambda deployment package v1.0"
git push origin v1.0

# 2. On GitHub web interface:
#    - Go to Releases → Create new release
#    - Select tag v1.0
#    - Upload lambda_deployment.zip as release asset
#    - Publish release

# 3. Students download with one command:
wget https://github.com/emadruga/javumbo/releases/download/v1.0/lambda_deployment.zip
```

---

## Instructor Workflow: Step-by-Step

### One-Time Setup (Before First Class)

**1. Build the deployment package:**
```bash
cd /Users/emadruga/proj/javumbo/server_lambda
./build_lambda_package.sh
```

**2. Upload to storage:**
```bash
# Option A: GitHub Releases (RECOMMENDED)
git tag -a v1.0 -m "Serverless v1.0"
git push origin v1.0
# Then upload lambda_deployment.zip on GitHub release page

# Option B: Google Drive/Dropbox
# Upload lambda_deployment.zip and share link

# Option C: Git LFS (if repo supports it)
git lfs track "server_lambda/lambda_deployment.zip"
git add .gitattributes server_lambda/lambda_deployment.zip
git commit -m "Add Lambda package"
git push
```

**3. Test deployment in fresh Learner Lab:**
```bash
# Start new Learner Lab
# Configure AWS CLI
# Download package
# Run ./deploy.sh
# Verify works
```

**4. Provide students with:**
- Repository URL: `https://github.com/emadruga/javumbo`
- Package download URL: `https://github.com/emadruga/javumbo/releases/download/v1.0/lambda_deployment.zip`
- Quick start doc: `docs/AWS_LEARNER_LAB_QUICKSTART.md`

### Each Lab Session (Students)

**Students execute these 3 commands:**

```bash
# 1. Clone repository
git clone https://github.com/emadruga/javumbo.git
cd javumbo/server_lambda

# 2. Download package
wget https://github.com/emadruga/javumbo/releases/download/v1.0/lambda_deployment.zip

# 3. Deploy (backend + frontend)
./deploy.sh
```

**Time: ~5-7 minutes total** (includes frontend build and deployment)

**What happens automatically:**
- Infrastructure deployed (S3 buckets, DynamoDB, Lambda, API Gateway)
- Lambda code uploaded
- **Frontend built with dynamic API endpoint URL**
- **Frontend uploaded to S3**
- Application ready to use in browser!

**No manual configuration needed** - the script handles everything including the changing API Gateway URLs.

### When Code Changes (Instructor)

**If you modify backend code (server_lambda/src/):**

```bash
# 1. Edit files in server_lambda/src/
# 2. Rebuild Lambda package
./build_lambda_package.sh

# 3. Test deployment (includes frontend)
./deploy.sh

# 4. Create new version
git tag -a v1.1 -m "Updated auth logic"
git push origin v1.1

# 5. Upload new lambda_deployment.zip to v1.1 release

# 6. Tell students to use v1.1:
wget https://github.com/emadruga/javumbo/releases/download/v1.1/lambda_deployment.zip
```

**If you modify frontend code (client_lambda/):**

```bash
# 1. Edit files in client_lambda/src/
# 2. Commit changes to git
git add client_lambda/
git commit -m "Updated UI"
git push

# 3. Students get changes automatically:
# - Next time they run ./deploy.sh, it pulls latest code
# - Frontend is rebuilt with their API endpoint
# - No new Lambda package needed!
```

**Key insight**: Frontend changes don't require rebuilding the Lambda package. The deploy script always builds the frontend from the latest code in the repository.

### After Lab Expires (Nothing!)

**No action required!** The package is safely stored in GitHub/Drive/Git. Next lab session uses the same package.

---

## Time Savings Analysis

| Scenario | Build Time | Deploy Time | Total Time |
|----------|------------|-------------|------------|
| **With preserved package** | 0 min (download: 30s) | 5 min | **~5-6 min** |
| **Without (rebuild)** | 10-15 min | 5 min | **15-20 min** |
| **Time saved per student** | - | - | **10-15 min** |
| **Time saved (30 students)** | - | - | **5-7.5 hours** |

---

## Storage Option Comparison

| Option | Cost | Bandwidth | Ease of Use | Best For |
|--------|------|-----------|-------------|----------|
| **GitHub Releases** | Free | Unlimited | ⭐⭐⭐⭐⭐ | **RECOMMENDED** - Easy downloads, versioned |
| **Git LFS** | Free* | 1GB/month | ⭐⭐⭐ | Automatic with `git clone`, limited bandwidth |
| **Google Drive** | Free | Unlimited | ⭐⭐⭐⭐ | Simple sharing, manual downloads |
| **AWS S3** | ~$3/year | Pay per GB | ⭐⭐ | AWS-native, requires personal account |

*Git LFS: Free tier = 1GB bandwidth/month. Exceeding requires upgrade ($5/month for 50GB).

**Recommendation: GitHub Releases** (free + unlimited + easy + versioned)

---

## Common Student Issues & Solutions

### "lambda_deployment.zip not found"
**Cause**: Student forgot to download it
**Fix**:
```bash
wget https://github.com/emadruga/javumbo/releases/download/v1.0/lambda_deployment.zip
```

### "Unable to import module 'lambda_handler'" (500 error)
**Cause**: Wrong package deployed (macOS binaries instead of Linux)
**Fix**: Re-download correct package or rebuild:
```bash
./build_lambda_package.sh
```

**Verify Linux binaries:**
```bash
unzip -l lambda_deployment.zip | grep bcrypt/_bcrypt.abi3.so
# Should show ~631,720 bytes (Linux)
# NOT ~616,000 bytes (macOS)
```

### "Endpoint not found" (404 error)
**Cause**: Old package with outdated routes
**Fix**: Re-download latest package from GitHub Releases

### "AWS credentials not configured"
**Cause**: Student didn't run `aws configure`
**Fix**:
```bash
aws configure
# Enter AWS Access Key ID and Secret from Learner Lab
```

### Deployment is slow
**Expected**: First Terraform apply takes 3-5 minutes (creates S3, DynamoDB, Lambda, API Gateway)
**Not an issue**, just wait for completion

---

## What Students Get After Deployment

### API Endpoint
```
https://XXXXXXXXXX.execute-api.us-east-1.amazonaws.com
```

### Available Routes
- `POST /api/register` - Create user account
- `POST /api/login` - Get JWT token
- `GET /api/decks` - List decks (authenticated)
- `POST /api/decks` - Create deck (authenticated)
- `POST /api/cards` - Add flashcard (authenticated)
- `GET /api/review` - Get next card for review
- `POST /api/review` - Submit review result
- `GET /api/export` - Export to Anki `.apkg` file

### Sample Usage
```bash
# Register
curl -X POST $API/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"student1","name":"Student","password":"password123456"}'

# Login
curl -X POST $API/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"student1","password":"password123456"}'

# Get token from login response, then:
TOKEN="eyJhbGci..."
curl -X GET $API/api/decks \
  -H "Authorization: Bearer $TOKEN"
```

---

## Architecture Overview

```
Student Browser
    ↓
API Gateway (HTTPS endpoint)
    ↓
Lambda Function (Flask app with JWT auth)
    ↓
    ├─→ S3 Bucket (user SQLite databases, .anki2 files)
    └─→ DynamoDB (users table, sessions table, locks table)
```

**Key Features:**
- **JWT Authentication**: Stateless, 1-hour token expiration
- **Session Caching**: Reduces S3 operations by 80%+ (5-minute cache)
- **Anki Compatibility**: Databases exportable to Anki Desktop
- **Spaced Repetition**: SM-2 algorithm for optimal learning intervals

---

## Costs

**Per deployment test** (one student, one session):
- Lambda invocations: ~50 requests = $0.00001
- S3 operations: ~20 requests = $0.0001
- DynamoDB: Free tier eligible
- **Total per student per session: <$0.001** (essentially free)

**Monthly costs** (10 active users, 100 reviews/day each):
- Lambda: ~$0.20
- S3 storage: ~$0.50
- DynamoDB: Free tier
- API Gateway: ~$0.10
- **Total: <$1/month**

**Learner Lab Budget:** Typically $50-100, enough for entire semester.

---

## Troubleshooting Resources

| Issue | Document to Check |
|-------|-------------------|
| Deployment problems | `DEPLOYMENT_GUIDE.md` |
| Package building errors | `AWS_LEARNER_LAB_ARTIFACT_PRESERVATION.md` |
| Student quick reference | `AWS_LEARNER_LAB_QUICKSTART.md` |
| API testing | `TESTING_THE_API_IN_AWS_LAMBDA.md` |
| Architecture details | `REFACTOR_WEEK_4.md` |

---

## Key Takeaways

✅ **Save `lambda_deployment.zip` before lab expires** (16MB file)

✅ **Upload to GitHub Releases** for easy student access

✅ **Students deploy in 5 minutes** with `./deploy.sh`

✅ **No rebuilding between sessions** - package is reusable

✅ **Time savings: 10-15 minutes per student** per deployment

✅ **Essentially free** within Learner Lab budgets

---

## Quick Reference Card

### For Instructors (Before First Class)
```bash
./build_lambda_package.sh                          # Build package
git tag -a v1.0 -m "v1.0" && git push origin v1.0  # Create tag
# Upload lambda_deployment.zip to GitHub release
```

### For Students (Every Lab Session)
```bash
git clone https://github.com/emadruga/javumbo.git
cd javumbo/server_lambda
wget https://github.com/.../v1.0/lambda_deployment.zip
./deploy.sh
```

### Clean Up (End of Session)
```bash
cd terraform
terraform destroy  # Optional, lab auto-cleans anyway
```

---

**Last Updated**: 2025-12-17
**Version**: 1.0
**Tested with**: AWS Academy Learner Lab, Python 3.11, Terraform 1.0+
