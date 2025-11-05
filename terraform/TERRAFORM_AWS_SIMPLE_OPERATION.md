# JAVUMBO AWS Terraform Operations Guide

This document provides step-by-step operational procedures for deploying, managing, debugging, and destroying the JAVUMBO application on AWS using Terraform.

---

## Table of Contents

1. [Initial Deployment](#initial-deployment)
2. [Verifying Deployment](#verifying-deployment)
3. [Accessing the Instance](#accessing-the-instance)
4. [Docker Management Commands](#docker-management-commands)
5. [Application Updates](#application-updates)
6. [Debugging & Troubleshooting](#debugging--troubleshooting)
7. [Stopping Services](#stopping-services)
8. [Destroying Infrastructure](#destroying-infrastructure)

---

## Initial Deployment

### Prerequisites

- Terraform installed (>= 1.0)
- AWS credentials configured (`aws configure`)
- SSH key pair at `~/.ssh/id_rsa.pub`

### Deployment Steps

```bash
# 1. Navigate to terraform directory
cd terraform

# 2. Initialize Terraform (download providers)
terraform init

# 3. Review the deployment plan
terraform plan

# 4. Deploy to AWS
terraform apply

# Review the resources to be created, then type: yes
```

**Deployment Time:** 2-3 minutes for infrastructure + 5-10 minutes for application installation via user-data script.

### After Deployment

Terraform will output important information:

```
Outputs:

application_url = "http://54.87.11.69"
instance_id = "i-079a30c71bcfd0244"
instance_public_ip = "54.87.11.69"
ssh_command = "ssh -i ~/.ssh/id_rsa ubuntu@54.87.11.69"
```

**Important:** Wait 5-10 minutes after `terraform apply` completes for the user-data script to finish installing Docker and building containers.

---

## Verifying Deployment

### Check Terraform Outputs

```bash
# View all outputs
terraform output

# View specific output
terraform output application_url
terraform output ssh_command
```

### Check Cloud-Init Status

```bash
# SSH into instance
ssh -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>

# Check if user-data script is still running
tail -f /var/log/cloud-init-output.log

# Look for this line at the end:
# "JAVUMBO deployment complete!"

# Check for errors
grep -i error /var/log/cloud-init-output.log
```

### Verify Docker Containers

```bash
# Check container status
cd /home/ubuntu/javumbo
sudo docker compose ps

# Should show:
# NAME               STATUS         PORTS
# flashcard_client   Up             0.0.0.0:80->80/tcp
# flashcard_server   Up             8000/tcp
```

### Test Application

```bash
# Test from instance
curl -I http://localhost/

# Should return: HTTP/1.1 200 OK
```

Open browser to `http://<instance_public_ip>` - you should see the JAVUMBO login page.

---

## Accessing the Instance

### SSH Access

```bash
# Using output from terraform
ssh -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>

# Or copy-paste the ssh_command output
terraform output -raw ssh_command | sh
```

### File Locations

```
/home/ubuntu/javumbo/                 # Application root
├── server/                           # Backend code
│   ├── .env                          # SECRET_KEY configuration
│   ├── app.py                        # Flask application
│   ├── admin.db                      # User credentials database
│   └── user_dbs/                     # User flashcard databases
│       └── user_1.db
├── client/                           # Frontend code
│   └── dist/                         # Built React app
└── docker-compose.yml                # Docker orchestration
```

---

## Docker Management Commands

All commands should be run from `/home/ubuntu/javumbo` directory.

### View Container Status

```bash
# List running containers
sudo docker compose ps

# List all containers (including stopped)
sudo docker ps -a

# Detailed container information
sudo docker inspect flashcard_server
sudo docker inspect flashcard_client
```

### View Logs

```bash
# View all logs
sudo docker compose logs

# Follow logs in real-time
sudo docker compose logs -f

# View logs for specific container
sudo docker logs flashcard_server
sudo docker logs flashcard_client

# Follow logs for specific container
sudo docker logs flashcard_server -f

# View last N lines
sudo docker logs flashcard_server --tail 50
```

### Restart Containers

```bash
# Restart all containers
sudo docker compose restart

# Restart specific container
sudo docker compose restart server
sudo docker compose restart client

# Stop and start (full restart)
sudo docker compose down
sudo docker compose up -d
```

### Rebuild Containers

```bash
# Rebuild all containers
sudo docker compose build

# Rebuild with no cache (clean build)
sudo docker compose build --no-cache

# Rebuild specific container
sudo docker compose build client --no-cache
sudo docker compose build server --no-cache

# Rebuild and restart
sudo docker compose up -d --build
```

### Execute Commands in Containers

```bash
# Execute command in running container
sudo docker exec flashcard_server ls -la /app

# Interactive shell in container
sudo docker exec -it flashcard_server /bin/bash

# Run Python in server container
sudo docker exec flashcard_server python3 -c "from app import init_admin_db; init_admin_db()"
```

### Container Resource Usage

```bash
# View resource usage
sudo docker stats

# View disk usage
sudo docker system df

# View container processes
sudo docker top flashcard_server
sudo docker top flashcard_client
```

---

## Application Updates

### Update Application Code

```bash
# SSH into instance
ssh -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>

# Navigate to app directory
cd /home/ubuntu/javumbo

# Pull latest code from git
git pull

# Check what changed
git log -3
git diff HEAD~1

# Rebuild affected containers
sudo docker compose build --no-cache

# Restart with new code
sudo docker compose up -d

# Verify update
sudo docker compose ps
sudo docker compose logs
```

### Update Only Frontend

```bash
cd /home/ubuntu/javumbo
git pull
sudo docker compose build client --no-cache
sudo docker compose up -d client
```

### Update Only Backend

```bash
cd /home/ubuntu/javumbo
git pull
sudo docker compose build server --no-cache
sudo docker compose up -d server
```

---

## Debugging & Troubleshooting

### Application Not Loading

**1. Check if containers are running:**
```bash
sudo docker compose ps
```

**2. Check nginx logs:**
```bash
sudo docker logs flashcard_client --tail 50
```

**3. Check backend logs:**
```bash
sudo docker logs flashcard_server --tail 50
```

**4. Test local connectivity:**
```bash
# Test nginx
curl -I http://localhost/

# Test backend through nginx
curl http://localhost/decks
```

### Connection Refused Errors

**Check port 80 is listening:**
```bash
sudo ss -tlnp | grep :80
# Should show: docker-proxy
```

**Check security group (from local machine):**
```bash
cd terraform
terraform show | grep -A 10 "ingress"
```

**Test from outside:**
```bash
# From local machine
curl -I http://<instance_public_ip>
telnet <instance_public_ip> 80
```

### Database Issues

**Check database files exist:**
```bash
ls -la /home/ubuntu/javumbo/server/admin.db
ls -la /home/ubuntu/javumbo/server/user_dbs/
```

**Check permissions:**
```bash
# Databases should be owned by root (container user)
ls -la /home/ubuntu/javumbo/server/*.db
```

**Initialize admin database manually:**
```bash
sudo docker exec flashcard_server python3 -c "from app import init_admin_db; init_admin_db()"
```

### Session/Login Issues

**Check session directory:**
```bash
ls -la /home/ubuntu/javumbo/server/flask_session/
```

**Check cookies in browser:**
- Open DevTools (F12)
- Go to Application tab
- Check Cookies for the site
- Look for `session` cookie

**Restart server to clear sessions:**
```bash
sudo docker compose restart server
```

### Build Failures

**View build logs:**
```bash
sudo docker compose build 2>&1 | tee build.log
```

**Common issues:**
- **npm build fails:** Check `client/Dockerfile` has `RUN npm ci` (not `npm ci --only=production`)
- **Python dependency fails:** Check `server/requirements.txt`
- **Out of disk space:** Run `sudo docker system prune -a`

**Clean Docker cache:**
```bash
# Remove unused images
sudo docker image prune -a

# Remove all stopped containers
sudo docker container prune

# Remove unused volumes
sudo docker volume prune

# Clean everything
sudo docker system prune -a --volumes
```

### Check User Data Script

**View full log:**
```bash
cat /var/log/cloud-init-output.log
```

**Check for errors:**
```bash
grep -i error /var/log/cloud-init-output.log
grep -i fail /var/log/cloud-init-output.log
```

**Verify Docker installed:**
```bash
docker --version
docker compose version
```

### Network Debugging

**Check nginx configuration:**
```bash
sudo docker exec flashcard_client cat /etc/nginx/conf.d/default.conf
```

**Test nginx configuration:**
```bash
sudo docker exec flashcard_client nginx -t
```

**Check container networking:**
```bash
sudo docker network ls
sudo docker network inspect javumbo_flashcard-net
```

**Check inter-container communication:**
```bash
# From client container to server
sudo docker exec flashcard_client wget -O- http://server:8000/
```

---

## Stopping Services

### Stop Containers (Keep Instance Running)

```bash
# SSH into instance
ssh -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>

cd /home/ubuntu/javumbo

# Stop all containers
sudo docker compose down

# Verify containers stopped
sudo docker compose ps
sudo docker ps -a
```

**To restart later:**
```bash
sudo docker compose up -d
```

### Stop EC2 Instance (from local machine)

```bash
# Get instance ID
cd terraform
terraform output instance_id

# Stop instance (keeps all data, stops billing for compute)
aws ec2 stop-instances --instance-ids <instance_id>

# Check status
aws ec2 describe-instances --instance-ids <instance_id> \
  --query 'Reservations[0].Instances[0].State.Name'
```

**To restart:**
```bash
aws ec2 start-instances --instance-ids <instance_id>

# Get new public IP (may have changed)
aws ec2 describe-instances --instance-ids <instance_id> \
  --query 'Reservations[0].Instances[0].PublicIpAddress'
```

---

## Destroying Infrastructure

### Full Destruction (Delete Everything)

**⚠️ WARNING:** This will permanently delete all data, including databases and user data!

```bash
# Navigate to terraform directory
cd terraform

# Preview what will be destroyed
terraform plan -destroy

# Destroy all resources
terraform destroy

# Review the destruction plan, then type: yes
```

**What gets deleted:**
- EC2 instance
- All databases (admin.db, user databases)
- VPC and networking components
- Security groups
- SSH key pair (in AWS, not your local key)

**What's preserved:**
- Local Terraform state files
- Your local git repository
- Your SSH keys

### Backup Before Destroying

```bash
# SSH into instance
ssh -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>

# Create backup archive
cd /home/ubuntu
tar -czf javumbo-backup-$(date +%Y%m%d).tar.gz javumbo/server/admin.db javumbo/server/user_dbs/

# Exit SSH
exit

# Download backup to local machine
scp -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>:/home/ubuntu/javumbo-backup-*.tar.gz .

# Now safe to destroy
cd terraform
terraform destroy
```

### Partial Cleanup

**Remove only the EC2 instance (keep networking):**
```bash
# Not recommended - use terraform destroy for full cleanup
terraform destroy -target=aws_instance.javumbo
```

**Clean Terraform state:**
```bash
# Remove cached plugins and state lock
rm -rf .terraform/
rm -f .terraform.lock.hcl
rm -f terraform.tfstate.backup

# Re-initialize
terraform init
```

---

## Quick Reference Commands

### Daily Operations

```bash
# SSH into instance
ssh -i ~/.ssh/id_rsa ubuntu@$(terraform output -raw instance_public_ip)

# Check status
cd /home/ubuntu/javumbo && sudo docker compose ps

# View logs
sudo docker compose logs -f

# Update app
git pull && sudo docker compose up -d --build

# Restart
sudo docker compose restart
```

### Emergency Recovery

```bash
# Stop everything
sudo docker compose down

# Clean Docker cache
sudo docker system prune -a

# Rebuild from scratch
cd /home/ubuntu/javumbo
sudo docker compose build --no-cache
sudo docker compose up -d

# Check logs
sudo docker compose logs -f
```

### Monitoring

```bash
# Check resource usage
sudo docker stats

# Check disk space
df -h

# Check system resources
htop  # or: top

# Check Docker disk usage
sudo docker system df
```

---

## Cost Management

### Current Setup Cost

- **EC2 t2.micro:** ~$8.50/month (FREE tier eligible for 12 months)
- **EBS 30GB gp3:** ~$2.40/month
- **Data transfer:** Variable
- **Total:** ~$11/month (or $0 with free tier)

### To Minimize Costs

1. **Stop instance when not in use:**
   ```bash
   aws ec2 stop-instances --instance-ids $(terraform output -raw instance_id)
   ```

2. **Destroy completely when done:**
   ```bash
   terraform destroy
   ```

3. **Use smaller instance type:**
   - Edit `terraform/variables.tf`
   - Change `instance_type` default from `t2.micro` to `t2.nano`

---

## Additional Resources

- **Terraform Documentation:** https://www.terraform.io/docs
- **Docker Compose Documentation:** https://docs.docker.com/compose/
- **AWS EC2 Documentation:** https://docs.aws.amazon.com/ec2/
- **Project README:** `../README.md`
- **Deployment Plan:** `./TERRAFORM_JAVUMBO_AWS_SIMPLE.md`
- **Quick Start:** `./QUICKSTART.md`

---

## Support & Issues

If you encounter issues:

1. Check logs (`sudo docker compose logs`)
2. Review troubleshooting section above
3. Check git repository issues
4. Verify AWS quotas and limits
5. Ensure AWS credentials are valid

**Common Solutions:**
- 90% of issues: Rebuild containers with `--no-cache`
- Session issues: Check `SESSION_COOKIE_SECURE` setting in `app.py`
- Build failures: Check Dockerfile has correct npm commands
- Network issues: Verify security group allows port 80

---

**Last Updated:** November 2025
**Version:** 1.0
**Deployment Method:** Docker Compose on single EC2 instance
