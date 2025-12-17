# AWS Learner Lab Artifact Preservation Guide

**For Instructors**: How to preserve deployment artifacts between AWS Learner Lab sessions so students don't need to rebuild packages.

---

## The Problem

AWS Learner Labs expire and are ephemeral:
- Labs auto-terminate after session ends
- All AWS resources are deleted
- Students get fresh AWS accounts each session
- **Building Lambda packages takes 10-15 minutes with Docker**

## The Solution

**Preserve the pre-built `lambda_deployment.zip` outside of AWS**, so students can deploy in 5 minutes instead of 15+ minutes.

---

## Before Lab Expiration: Critical Artifacts to Save

### 1. Lambda Deployment Package (CRITICAL ⚠️)

**File**: `server_lambda/lambda_deployment.zip`
**Size**: ~16-17 MB
**Contains**: All Python dependencies + application code (Linux binaries for AWS Lambda)

**Why critical**: Building this requires Docker and takes 10-15 minutes. Without it, students must rebuild every session.

**How to save**:

```bash
# Option A: Commit to Git (if <100MB)
cd /Users/emadruga/proj/javumbo
git add server_lambda/lambda_deployment.zip
git commit -m "Add pre-built Lambda deployment package for students"
git push

# Option B: Upload to GitHub Releases
# 1. Create a release on GitHub
# 2. Upload lambda_deployment.zip as release asset
# 3. Students download with:
#    wget https://github.com/emadruga/javumbo/releases/download/v1.0/lambda_deployment.zip

# Option C: Copy to external storage
cp server_lambda/lambda_deployment.zip ~/Dropbox/javumbo_teaching/lambda_deployment_$(date +%Y%m%d).zip
# Or: Google Drive, OneDrive, etc.

# Option D: Personal S3 bucket (outside Learner Lab)
aws s3 cp server_lambda/lambda_deployment.zip \
  s3://your-permanent-bucket/javumbo/lambda_deployment.zip \
  --profile personal-aws-account
```

### 2. Terraform State (OPTIONAL, for reference)

**File**: `server_lambda/terraform/terraform.tfstate`
**Purpose**: Record of what was deployed in this session
**Why save**: Helps troubleshoot issues, but NOT needed for next session

```bash
cp server_lambda/terraform/terraform.tfstate \
  ~/backups/terraform_state_$(date +%Y%m%d).tfstate
```

### 3. Sample User Data (OPTIONAL, for demos)

If you want to show students a pre-populated database:

```bash
# Download from S3 before lab expires
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws s3 cp s3://javumbo-user-dbs-${ACCOUNT_ID}/user_dbs/testuser2025.anki2 \
  ~/backups/sample_user_$(date +%Y%m%d).anki2

# Export DynamoDB users table (optional)
aws dynamodb scan --table-name javumbo-users \
  > ~/backups/users_backup_$(date +%Y%m%d).json
```

---

## Recommended Storage Options (Ranked)

### Option 1: GitHub Releases (BEST for students)

**Pros:**
- ✅ Versioned and always available
- ✅ Easy download with `wget` or `curl`
- ✅ Free for public repos
- ✅ Students already know GitHub

**Cons:**
- ❌ Requires creating releases manually
- ❌ File size limits (2GB, plenty for us)

**Setup:**

```bash
# 1. Create tag
git tag -a v1.0 -m "Lambda deployment package v1.0"
git push origin v1.0

# 2. On GitHub: Create release from tag
# 3. Upload lambda_deployment.zip as release asset

# Students download:
wget https://github.com/emadruga/javumbo/releases/download/v1.0/lambda_deployment.zip
```

### Option 2: Git LFS (BEST for frequent updates)

**Pros:**
- ✅ Version controlled with code
- ✅ Students get it automatically with `git clone`
- ✅ No manual uploads

**Cons:**
- ❌ Requires Git LFS installation
- ❌ Limited free bandwidth (1GB/month on GitHub Free)

**Setup:**

```bash
# One-time setup
cd /Users/emadruga/proj/javumbo
git lfs install
git lfs track "server_lambda/lambda_deployment.zip"
git add .gitattributes server_lambda/lambda_deployment.zip
git commit -m "Track Lambda package with Git LFS"
git push

# Students clone:
git clone https://github.com/emadruga/javumbo.git  # LFS files downloaded automatically
```

### Option 3: Google Drive / Dropbox (SIMPLEST)

**Pros:**
- ✅ Very simple to use
- ✅ Shareable links
- ✅ Large storage quotas

**Cons:**
- ❌ Manual downloads
- ❌ Not version controlled
- ❌ Link management

**Setup:**

```bash
# 1. Upload to Google Drive / Dropbox
# 2. Generate shareable link (anyone with link can view)
# 3. Students download:
curl -L "YOUR_SHAREABLE_LINK" -o lambda_deployment.zip
```

### Option 4: Personal AWS S3 (For advanced users)

**Pros:**
- ✅ AWS-native solution
- ✅ Fast downloads
- ✅ No bandwidth limits

**Cons:**
- ❌ Requires personal AWS account (outside Learner Lab)
- ❌ Costs money (~$0.023/GB storage + transfer)

**Setup:**

```bash
# Upload to personal S3
aws s3 cp lambda_deployment.zip \
  s3://your-bucket/javumbo/lambda_deployment.zip \
  --acl public-read \
  --profile personal-account

# Students download:
wget https://your-bucket.s3.amazonaws.com/javumbo/lambda_deployment.zip
```

---

## Instructor Workflow: Complete Process

### Before First Lab Session

**1. Build the deployment package ONCE:**

```bash
cd /Users/emadruga/proj/javumbo/server_lambda
./build_lambda_package.sh
```

**2. Upload to chosen storage:**

```bash
# Example: GitHub Releases
git tag -a v1.0 -m "Serverless deployment v1.0"
git push origin v1.0
# Then upload lambda_deployment.zip to GitHub release page
```

**3. Update deployment script with download URL:**

Edit `server_lambda/deploy.sh` to include download instructions:

```bash
if [ ! -f "lambda_deployment.zip" ]; then
    echo "❌ lambda_deployment.zip not found!"
    echo ""
    echo "Download from:"
    echo "  wget https://github.com/emadruga/javumbo/releases/download/v1.0/lambda_deployment.zip"
    echo ""
    exit 1
fi
```

**4. Test in fresh Learner Lab:**

- Start new Learner Lab
- Clone repository
- Download `lambda_deployment.zip`
- Run `./deploy.sh`
- Verify deployment works

### During Each Lab Session

**Students execute:**

```bash
# 1. Clone repository
git clone https://github.com/emadruga/javumbo.git
cd javumbo/server_lambda

# 2. Download package
wget https://github.com/emadruga/javumbo/releases/download/v1.0/lambda_deployment.zip

# 3. Deploy
./deploy.sh
```

**Time: ~5 minutes** (vs 15+ minutes rebuilding)

### After Lab Expires

**Nothing to do!**

The package is safely stored in Git/GitHub/Drive. Next session starts fresh with the same package.

### When Code Changes

**Rebuild and re-upload:**

```bash
# 1. Make code changes in server_lambda/src/
# 2. Rebuild package
./build_lambda_package.sh

# 3. Test locally
./deploy.sh

# 4. Create new version
git tag -a v1.1 -m "Updated authentication logic"
git push origin v1.1

# 5. Upload new lambda_deployment.zip to v1.1 release

# 6. Update instructions for students:
#    wget https://github.com/emadruga/javumbo/releases/download/v1.1/lambda_deployment.zip
```

---

## Troubleshooting Preserved Artifacts

### Package fails with "invalid ELF header"

**Problem**: Package has macOS binaries instead of Linux binaries
**Cause**: Package was built with `pip install` instead of Docker
**Fix**: Rebuild with Docker:

```bash
./build_lambda_package.sh
```

**Verify Linux binaries:**

```bash
unzip -l lambda_deployment.zip | grep bcrypt/_bcrypt.abi3.so
# Should show ~631,720 bytes (Linux binary)
# If ~616,000 bytes = macOS binary (WRONG!)
```

### Git LFS bandwidth quota exceeded

**Problem**: GitHub LFS bandwidth limit (1GB/month on free tier)
**Solutions**:
- Switch to GitHub Releases (no bandwidth limits)
- Upgrade to GitHub Pro ($4/month, 50GB bandwidth)
- Host on S3 or Google Drive

### Package download is slow

**Problem**: Large file (16MB) over slow connection
**Solutions**:
- Use CDN (GitHub Releases has CDN)
- Compress further with `gzip` (saves ~20%)
- Host on faster service (S3, CloudFront)

---

## Advanced: Multi-Version Management

For classes with different semesters or versions:

```bash
# Directory structure
javumbo_packages/
├── v1.0_fall2024/
│   └── lambda_deployment.zip
├── v1.1_spring2025/
│   └── lambda_deployment.zip
└── v2.0_advanced_class/
    └── lambda_deployment.zip

# Or use Git tags:
v1.0-fall2024
v1.1-spring2025
v2.0-advanced
```

Students download specific version:

```bash
wget https://github.com/emadruga/javumbo/releases/download/v1.0-fall2024/lambda_deployment.zip
```

---

## Cost Analysis: Storage Options

| Option | Storage Cost | Bandwidth Cost | Total/Year |
|--------|--------------|----------------|------------|
| GitHub Releases | Free | Free (unlimited) | **$0** |
| Git LFS (Free) | Free | 1GB/month free | **$0** (if under limit) |
| Google Drive (Free) | 15GB free | Free | **$0** |
| AWS S3 | $0.023/GB/month | $0.09/GB egress | ~$3/year |

**Recommendation**: GitHub Releases (free + unlimited bandwidth)

---

## Checklist: Before Lab Expires

- [ ] Copy `lambda_deployment.zip` to permanent storage
- [ ] Verify package is downloadable by students
- [ ] Update README/docs with download URL
- [ ] (Optional) Save terraform state for records
- [ ] (Optional) Export sample user databases
- [ ] Test download + deploy in fresh environment

---

## Summary

**Critical Artifact**: `lambda_deployment.zip` (16MB)

**Best Storage**: GitHub Releases (free, fast, versioned)

**Student Workflow**:
1. Download package (30 seconds)
2. Run `./deploy.sh` (5 minutes)
3. Total: **~5-6 minutes**

**Without Preservation**:
1. Build package with Docker (10-15 minutes)
2. Deploy (5 minutes)
3. Total: **~15-20 minutes**

**Time Saved**: 10-15 minutes per deployment x number of students

---

**Last Updated**: 2025-12-17
**For**: AWS Academy Learner Lab environments
**Tested with**: Python 3.11, AWS Lambda, Terraform
