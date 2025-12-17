# AWS Learner Lab Documentation - Navigation Guide

**Quick navigation** for AWS Learner Lab deployment documentation.

---

## 📚 For Instructors

Start here if you're teaching this material:

### **1. Quick Overview (Read First)**
**File**: [`AWS_LEARNER_LAB_OVERVIEW_FOR_INSTRUCTORS.md`](AWS_LEARNER_LAB_OVERVIEW_FOR_INSTRUCTORS.md)
- Complete overview and quick reference
- Time savings analysis
- Storage option comparison
- Quick reference cards
- **Read time: 10 minutes**

### **2. Detailed Artifact Preservation**
**File**: [`AWS_LEARNER_LAB_ARTIFACT_PRESERVATION.md`](AWS_LEARNER_LAB_ARTIFACT_PRESERVATION.md)
- What to save before lab expires
- Storage options (GitHub Releases, Git LFS, Drive, S3) with code examples
- Complete instructor workflow
- Multi-version management
- Troubleshooting preserved artifacts
- **Read time: 15 minutes**

### **3. Complete Deployment Guide**
**File**: [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md)
- Option A: Use pre-built package
- Option B: Rebuild from scratch
- Automated deployment script details
- Troubleshooting common issues
- **Read time: 20 minutes**

---

## 👨‍🎓 For Students

Start here if you're deploying in a Learner Lab:

### **Quick Start (Fastest Path)**
**File**: [`AWS_LEARNER_LAB_QUICKSTART.md`](AWS_LEARNER_LAB_QUICKSTART.md)
- 3-step deployment process
- Prerequisites checklist
- Testing commands
- Common issues & fixes
- **Read time: 5 minutes**
- **Deploy time: 5 minutes**

### **Complete Deployment Guide**
**File**: [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md)
- Detailed deployment instructions
- Troubleshooting section
- Best practices
- **Read time: 15 minutes**

---

## 🛠️ Automation Scripts

Located in `server_lambda/` (parent directory):

### **`deploy.sh`** - Deploy Everything
**Purpose**: Students run this every new Learner Lab session

**Usage**:
```bash
cd server_lambda
./deploy.sh
```

**What it does**:
1. Checks prerequisites (AWS CLI, Terraform, credentials)
2. Verifies `lambda_deployment.zip` exists and is valid
3. Deploys infrastructure with Terraform
4. Uploads Lambda code
5. Tests deployment
6. Displays API endpoint and quick start commands

**Time**: ~5 minutes

### **`build_lambda_package.sh`** - Build Lambda Package
**Purpose**: Instructor runs this to create/update `lambda_deployment.zip`

**Usage**:
```bash
cd server_lambda
./build_lambda_package.sh
```

**What it does**:
1. Cleans old artifacts
2. Uses Docker to install Linux binaries
3. Creates deployment package
4. Verifies package structure (critical files, Linux binaries)
5. Displays package details

**Time**: ~10-15 minutes

---

## 📖 Additional Documentation

### **Testing Guide**
**File**: [`TESTING_THE_API_IN_AWS_LAMBDA.md`](TESTING_THE_API_IN_AWS_LAMBDA.md)
- API testing procedures
- Manual testing workflows
- CloudWatch log analysis

### **Development History**
**File**: [`REFACTOR_WEEK_4.md`](REFACTOR_WEEK_4.md)
- Week 4 development log
- Frontend deployment
- Session management implementation
- Bug fixes and lessons learned

---

## 🎯 Quick Reference: What to Read When

### **"I'm teaching this class for the first time"**
1. Read: `AWS_LEARNER_LAB_OVERVIEW_FOR_INSTRUCTORS.md`
2. Read: `AWS_LEARNER_LAB_ARTIFACT_PRESERVATION.md`
3. Test deployment: Follow `AWS_LEARNER_LAB_QUICKSTART.md`

### **"I'm a student deploying in Learner Lab"**
1. Read: `AWS_LEARNER_LAB_QUICKSTART.md`
2. Run: `./deploy.sh`
3. If issues: Check `DEPLOYMENT_GUIDE.md` troubleshooting section

### **"The lab is about to expire, what do I save?"**
1. Read: Section 1 of `AWS_LEARNER_LAB_ARTIFACT_PRESERVATION.md`
2. Save: `lambda_deployment.zip` to GitHub Releases or Drive
3. That's it!

### **"I modified the code, what now?"**
1. Run: `./build_lambda_package.sh`
2. Test: `./deploy.sh`
3. Upload: New `lambda_deployment.zip` to new GitHub release tag
4. Read: "When Code Changes" in `AWS_LEARNER_LAB_OVERVIEW_FOR_INSTRUCTORS.md`

### **"Students are getting errors during deployment"**
1. Check: "Common Student Issues & Solutions" in `AWS_LEARNER_LAB_OVERVIEW_FOR_INSTRUCTORS.md`
2. Check: "Troubleshooting" section in `DEPLOYMENT_GUIDE.md`
3. Check: CloudWatch logs with `aws logs tail /aws/lambda/javumbo-api --since 10m --follow`

---

## 📊 Documentation Map

```
server_lambda/
├── deploy.sh                           # Student deployment script
├── build_lambda_package.sh             # Package build script
└── docs/
    ├── README_AWS_LEARNER_LAB.md      # This file (navigation guide)
    ├── AWS_LEARNER_LAB_OVERVIEW_FOR_INSTRUCTORS.md  # Instructor overview
    ├── AWS_LEARNER_LAB_ARTIFACT_PRESERVATION.md     # Artifact preservation
    ├── AWS_LEARNER_LAB_QUICKSTART.md               # Student quick start
    ├── DEPLOYMENT_GUIDE.md                          # Complete deployment
    ├── TESTING_THE_API_IN_AWS_LAMBDA.md            # API testing
    └── REFACTOR_WEEK_4.md                          # Development history
```

---

## 🔗 External Resources

- **AWS Learner Lab**: https://awsacademy.instructure.com/
- **Terraform**: https://www.terraform.io/
- **AWS Lambda**: https://aws.amazon.com/lambda/
- **GitHub Releases**: https://docs.github.com/en/repositories/releasing-projects-on-github

---

## ✅ Checklist: First-Time Instructor Setup

- [ ] Read `AWS_LEARNER_LAB_OVERVIEW_FOR_INSTRUCTORS.md`
- [ ] Build package: `./build_lambda_package.sh`
- [ ] Create GitHub release tag (v1.0)
- [ ] Upload `lambda_deployment.zip` to release
- [ ] Test deployment in fresh Learner Lab
- [ ] Share repository URL and package download URL with students
- [ ] Point students to `AWS_LEARNER_LAB_QUICKSTART.md`

---

## ✅ Checklist: First-Time Student Deployment

- [ ] Start AWS Learner Lab session
- [ ] Configure AWS CLI: `aws configure`
- [ ] Clone repository
- [ ] Download `lambda_deployment.zip`
- [ ] Run `./deploy.sh`
- [ ] Test API endpoint
- [ ] Celebrate! 🎉

---

**Need help?** Check the troubleshooting sections in each document, or contact the instructor.

**Last Updated**: 2025-12-17
