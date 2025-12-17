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

## Backing Up User Data (DynamoDB + S3)

When you need to preserve user data between deployments (testing, lab expiration, etc.), you must back up both DynamoDB tables and S3 user databases.

### Problem: User Data is Ephemeral

AWS Learner Labs are ephemeral, which means:
- DynamoDB tables are deleted when you run `terraform destroy`
- S3 user database files are deleted when buckets are emptied
- User accounts, sessions, and flashcard data are lost
- **Students lose all their progress!**

### Solution: Comprehensive Backup Script

We've created a Python script that backs up everything needed to restore user data:

**File**: `server_lambda/backup_deployment.py`

**What it backs up**:
1. Lambda deployment package (`lambda_deployment.zip`)
2. Terraform state files (for infrastructure recreation)
3. **DynamoDB tables** (javumbo-users, javumbo-sessions, javumbo-user-locks)
4. **S3 user database files** (all `.anki2` files)
5. **Creates README** with deployment information

**Usage**:

```bash
cd /Users/emadruga/proj/javumbo/server_lambda

# Run the backup script BEFORE tearing down infrastructure
python3 backup_deployment.py
```

**Example Output**:
```
📦 Javumbo Deployment Backup Script
============================================================
📂 Creating backup directory: deployments/backup_20251217_194204/

1️⃣  Backing up Lambda deployment package...
   ✅ Saved: lambda_deployment-20251217.zip (16.2 MB)

2️⃣  Backing up Terraform state...
   ✅ Saved: terraform.tfstate (44.5 KB)

3️⃣  Backing up DynamoDB tables...
   📥 Backing up table: javumbo-users
      Items: 2
      ✅ Saved: javumbo-users_backup.json (1.2 KB)
   📥 Backing up table: javumbo-sessions
      Items: 3
      ✅ Saved: javumbo-sessions_backup.json (2.4 KB)
   📥 Backing up table: javumbo-user-locks
      Items: 0
      ✅ Saved: javumbo-user-locks_backup.json (0.1 KB)

4️⃣  Backing up S3 user databases...
   ☁️  Found 2 user database files
      ✅ Downloaded: malkai.anki2
      ✅ Downloaded: testuser.anki2

5️⃣  Creating backup README...
   ✅ Created: README.md

============================================================
✅ Backup complete!

Backup location: deployments/backup_20251217_194204/
Backup size: 16.5 MB

Next steps:
  • Keep this backup in a safe location
  • Use these files to restore after redeployment
  • See README.md in backup directory for restore instructions
```

**Backup Directory Structure**:
```
deployments/backup_20251217_194204/
├── README.md                          # Deployment info and restore instructions
├── lambda_deployment-20251217.zip     # Lambda package (16 MB)
├── terraform.tfstate                  # Terraform state
├── javumbo-users_backup.json          # User accounts
├── javumbo-sessions_backup.json       # Active sessions
├── javumbo-user-locks_backup.json     # Database locks
└── user_dbs/                          # User flashcard databases
    ├── malkai.anki2
    └── testuser.anki2
```

### Restoring DynamoDB Data After Redeployment

After you've deployed the infrastructure with `./deploy.sh`, you can restore the DynamoDB data:

**File**: `server_lambda/restore_dynamodb.py`

**Usage**:

```bash
cd /Users/emadruga/proj/javumbo/server_lambda

# Restore from a specific backup directory
python3 restore_dynamodb.py deployments/backup_20251217_194204/
```

**Example Output**:
```
🔄 Javumbo DynamoDB Restore Script
============================================================
📂 Backup directory: deployments/backup_20251217_194204/

Found 3 backup file(s):
  • javumbo-users_backup.json
  • javumbo-sessions_backup.json
  • javumbo-user-locks_backup.json

⚠️  This will overwrite existing data. Continue? (yes/no): yes

📥 Restoring from: javumbo-users_backup.json
   Table: javumbo-users
   Items to restore: 2
   📝 Restored 2/2 items
   ✅ Restored 2 items to javumbo-users

📥 Restoring from: javumbo-sessions_backup.json
   Table: javumbo-sessions
   Items to restore: 3
   📝 Restored 3/3 items
   ✅ Restored 3 items to javumbo-sessions

📥 Restoring from: javumbo-user-locks_backup.json
   Table: javumbo-user-locks
   Items to restore: 0
   ⚠️  No items to restore

============================================================
✅ All tables restored successfully!

Next steps:
  • Test application to verify data was restored correctly
  • Check user login with restored credentials
```

### Restoring S3 User Databases

After restoring DynamoDB data, you should also restore user database files to S3:

```bash
cd /Users/emadruga/proj/javumbo/server_lambda/deployments/backup_20251217_194204/user_dbs

# Get your account ID and bucket name
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="javumbo-user-dbs-${ACCOUNT_ID}"

# Upload all user databases
aws s3 sync . s3://${BUCKET_NAME}/user_dbs/

# Verify upload
aws s3 ls s3://${BUCKET_NAME}/user_dbs/
```

### Complete Backup and Restore Workflow

**Before tearing down infrastructure**:
```bash
cd /Users/emadruga/proj/javumbo/server_lambda

# 1. Back up everything (DynamoDB + S3 + Lambda package)
python3 backup_deployment.py

# 2. Clean up S3 buckets
python3 cleanup_s3.py

# 3. Destroy infrastructure
cd terraform
terraform destroy -auto-approve
```

**After redeployment**:
```bash
cd /Users/emadruga/proj/javumbo/server_lambda

# 1. Deploy fresh infrastructure
./deploy.sh

# 2. Restore DynamoDB data
python3 restore_dynamodb.py deployments/backup_20251217_194204/

# 3. Restore S3 user databases
cd deployments/backup_20251217_194204/user_dbs
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3 sync . s3://javumbo-user-dbs-${ACCOUNT_ID}/user_dbs/

# 4. Test login with restored user
# Users should now be able to login with their previous credentials!
```

---

## Usage: Step-by-Step Workflows

### Scenario 1: Preserving User Data Between Lab Sessions

**Use case**: You have users with data and need to end your AWS Learner Lab session, but want to restore everything in the next session.

**Steps**:

1. **Before ending your lab session** (with AWS Learner Lab credentials active):
   ```bash
   cd /Users/emadruga/proj/javumbo/server_lambda

   # Activate conda environment (if using cleanup script)
   source ~/miniconda3/bin/activate
   conda activate AWS_BILLING

   # Back up everything
   python3 backup_deployment.py
   ```

   This creates a timestamped backup directory like `deployments/backup_20251217_194204/` containing:
   - Lambda deployment package
   - Terraform state
   - DynamoDB tables (users, sessions, locks)
   - S3 user database files (.anki2 files)

2. **Clean up and destroy** (to avoid charges):
   ```bash
   # Clean S3 buckets
   python3 cleanup_s3.py

   # Destroy infrastructure
   cd terraform
   terraform destroy -auto-approve
   ```

3. **In your next lab session** (with new AWS Learner Lab credentials):
   ```bash
   cd /Users/emadruga/proj/javumbo/server_lambda

   # Deploy fresh infrastructure
   ./deploy.sh
   # When prompted, type "yes" to confirm deployment

   # Wait for deployment to complete, then restore data
   # Activate conda environment
   source ~/miniconda3/bin/activate
   conda activate AWS_BILLING

   # Restore DynamoDB tables
   python3 restore_dynamodb.py deployments/backup_20251217_194204/
   # When prompted, type "yes" to confirm restore

   # Restore user database files to S3
   cd deployments/backup_20251217_194204/user_dbs
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   aws s3 sync . s3://javumbo-user-dbs-${ACCOUNT_ID}/user_dbs/

   # Verify
   aws s3 ls s3://javumbo-user-dbs-${ACCOUNT_ID}/user_dbs/
   ```

4. **Test that users can login**:
   ```bash
   # Get the new API endpoint from deploy output
   API_ENDPOINT="https://YOUR_NEW_API_ID.execute-api.us-east-1.amazonaws.com"

   # Test login with restored user (e.g., 'malkai' from backup)
   curl -X POST ${API_ENDPOINT}/api/login \
     -H "Content-Type: application/json" \
     -d '{"username":"malkai","password":"THEIR_PASSWORD"}'
   # Should return access_token if successful
   ```

---

### Scenario 2: Testing Complete Tear-Down and Rebuild

**Use case**: You want to test that your deployment procedure works from scratch, simulating a fresh AWS Learner Lab environment.

**Steps**:

1. **Create a backup first** (safety):
   ```bash
   cd /Users/emadruga/proj/javumbo/server_lambda
   source ~/miniconda3/bin/activate
   conda activate AWS_BILLING
   python3 backup_deployment.py
   ```

2. **Tear everything down**:
   ```bash
   # Clean S3 buckets
   python3 cleanup_s3.py

   # Destroy all infrastructure
   cd terraform
   terraform destroy -auto-approve
   ```

3. **Rebuild from scratch**:
   ```bash
   cd /Users/emadruga/proj/javumbo/server_lambda

   # Run complete deployment
   ./deploy.sh
   ```

   The script will:
   - Check prerequisites (AWS CLI, Terraform, npm)
   - Verify lambda_deployment.zip exists
   - Deploy infrastructure with Terraform
   - Upload Lambda code
   - Build and deploy frontend with correct API endpoint
   - Test the deployment

   **Expected output**: `✅ ✅ ✅ DEPLOYMENT SUCCESSFUL! ✅ ✅ ✅`

4. **(Optional) Restore previous data**:
   ```bash
   source ~/miniconda3/bin/activate
   conda activate AWS_BILLING
   python3 restore_dynamodb.py deployments/backup_20251217_194204/

   cd deployments/backup_20251217_194204/user_dbs
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   aws s3 sync . s3://javumbo-user-dbs-${ACCOUNT_ID}/user_dbs/
   ```

---

### Scenario 3: Just Backing Up DynamoDB User Data

**Use case**: You only want to back up user account data, not the entire infrastructure.

**Steps**:

1. **Using the full backup script** (easiest):
   ```bash
   cd /Users/emadruga/proj/javumbo/server_lambda
   source ~/miniconda3/bin/activate
   conda activate AWS_BILLING
   python3 backup_deployment.py
   ```

   The DynamoDB backup files will be in:
   - `deployments/backup_TIMESTAMP/javumbo-users_backup.json`
   - `deployments/backup_TIMESTAMP/javumbo-sessions_backup.json`
   - `deployments/backup_TIMESTAMP/javumbo-user-locks_backup.json`

2. **Manual DynamoDB backup** (alternative):
   ```bash
   # Back up users table
   aws dynamodb scan --table-name javumbo-users \
     --region us-east-1 > users_backup.json

   # Back up sessions table
   aws dynamodb scan --table-name javumbo-sessions \
     --region us-east-1 > sessions_backup.json

   # Back up locks table
   aws dynamodb scan --table-name javumbo-user-locks \
     --region us-east-1 > locks_backup.json
   ```

3. **Restore DynamoDB data later**:
   ```bash
   # After redeployment
   source ~/miniconda3/bin/activate
   conda activate AWS_BILLING
   python3 restore_dynamodb.py deployments/backup_TIMESTAMP/
   ```

---

### Scenario 4: Cleaning Up at End of Semester

**Use case**: Semester is over, need to archive everything and tear down completely.

**Steps**:

1. **Create final backup**:
   ```bash
   cd /Users/emadruga/proj/javumbo/server_lambda
   source ~/miniconda3/bin/activate
   conda activate AWS_BILLING
   python3 backup_deployment.py
   ```

2. **Copy backup to permanent storage**:
   ```bash
   # Copy to external location
   cp -r deployments/backup_20251217_194204/ ~/Dropbox/javumbo_semester_backup/

   # Or create archive
   tar -czf javumbo_final_backup.tar.gz deployments/backup_20251217_194204/
   mv javumbo_final_backup.tar.gz ~/Documents/
   ```

3. **Verify backup is safe**:
   ```bash
   ls -lh ~/Dropbox/javumbo_semester_backup/
   # Or
   tar -tzf ~/Documents/javumbo_final_backup.tar.gz | head -20
   ```

4. **Tear down everything**:
   ```bash
   python3 cleanup_s3.py
   cd terraform
   terraform destroy -auto-approve
   ```

5. **Verify cleanup in AWS Console**:
   - Check S3: No javumbo buckets should exist
   - Check DynamoDB: No javumbo tables should exist
   - Check Lambda: No javumbo-api function should exist
   - Check API Gateway: No javumbo-api gateway should exist

---

## Important Notes for conda Environment

When using the backup, restore, and cleanup scripts, you **must** activate the `AWS_BILLING` conda environment first, as it has the `boto3` library installed:

```bash
# Always run this before backup/restore/cleanup scripts
source ~/miniconda3/bin/activate
conda activate AWS_BILLING
```

Without this environment:
- `backup_deployment.py` will fail with "ModuleNotFoundError: No module named 'boto3'"
- `restore_dynamodb.py` will fail with the same error
- `cleanup_s3.py` will fail with the same error

The `deploy.sh` script does **not** require conda activation, as it uses AWS CLI directly.

---

## Cleaning Up AWS Resources

When you need to tear down all AWS resources (for testing or end of semester), you'll need to empty S3 buckets before Terraform can delete them.

### Problem: S3 Buckets with Versioning

The `javumbo-user-dbs` bucket has versioning enabled, which means:
- Regular `aws s3 rm --recursive` doesn't delete old versions
- Terraform destroy fails with "BucketNotEmpty" error
- Manual deletion of versions is complex

### Solution: Use the Cleanup Script

We've created a Python script to handle this automatically:

**File**: `server_lambda/cleanup_s3.py`

**Usage**:

```bash
cd /Users/emadruga/proj/javumbo/server_lambda

# Make it executable
chmod +x cleanup_s3.py

# Run the cleanup script
python3 cleanup_s3.py

# Then destroy with terraform
cd terraform
terraform destroy -auto-approve
```

**What the script does**:
1. Deletes all object versions from both S3 buckets
2. Deletes all delete markers
3. Leaves the buckets empty so Terraform can delete them
4. Handles pagination for large buckets

**Example Output**:
```
🧹 Javumbo S3 Cleanup Script
==================================================
🗑️  Deleting all objects from bucket: javumbo-user-dbs-540966371089
   Bucket is versioned - will delete all versions
   Deleting 4 object versions...
   ✅ Deleted 4 objects/versions

🗑️  Deleting all objects from bucket: javumbo-frontend-prod-540966371089
   Deleting 15 object versions...
   ✅ Deleted 15 objects/versions

✅ Cleanup complete!

Now you can run: terraform destroy -auto-approve
```

### Alternative: Manual Cleanup

If you prefer not to use the Python script:

```bash
# Force remove bucket (deletes all versions)
aws s3 rb s3://javumbo-user-dbs-ACCOUNT_ID --force
aws s3 rb s3://javumbo-frontend-prod-ACCOUNT_ID --force

# Then clean up Terraform state
cd terraform
terraform destroy -auto-approve
```

---

## Checklist: Before Lab Expires

- [ ] Copy `lambda_deployment.zip` to permanent storage
- [ ] Verify package is downloadable by students
- [ ] Update README/docs with download URL
- [ ] (Optional) Save terraform state for records
- [ ] (Optional) Export sample user databases
- [ ] Test download + deploy in fresh environment

---

## Checklist: When Tearing Down Infrastructure (Preserving User Data)

- [ ] Run `python3 backup_deployment.py` to back up everything (DynamoDB + S3 + Lambda)
- [ ] Verify backup was created in `deployments/backup_TIMESTAMP/` directory
- [ ] Run `python3 cleanup_s3.py` to empty S3 buckets
- [ ] Run `terraform destroy -auto-approve` to delete all resources
- [ ] Verify all resources are deleted in AWS Console
- [ ] Keep the backup directory safe for future restore

---

## Checklist: After Redeployment (Restoring User Data)

- [ ] Run `./deploy.sh` to deploy fresh infrastructure
- [ ] Verify deployment succeeded and API is accessible
- [ ] Run `python3 restore_dynamodb.py deployments/backup_TIMESTAMP/` to restore DynamoDB tables
- [ ] Run `aws s3 sync` to restore user database files to S3 (see Restoring S3 User Databases section)
- [ ] Test user login with previously registered credentials
- [ ] Verify user flashcards are accessible

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
