# JAVUMBO AWS Terraform Deployment

This directory contains Terraform configuration to deploy the JAVUMBO flashcard application to AWS using Docker Compose on a single EC2 instance.

## Prerequisites

1. **Terraform**: Install Terraform (version >= 1.0)
   ```bash
   # macOS
   brew install terraform

   # Linux
   wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
   unzip terraform_1.6.0_linux_amd64.zip
   sudo mv terraform /usr/local/bin/
   ```

2. **AWS CLI**: Configure AWS credentials
   ```bash
   aws configure
   # Enter your AWS Access Key ID, Secret Access Key, and default region
   ```

3. **SSH Key**: Ensure you have an SSH key pair at `~/.ssh/id_rsa.pub`
   ```bash
   # Generate if you don't have one
   ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
   ```

## Configuration

You can customize the deployment by modifying values in `variables.tf` or by creating a `terraform.tfvars` file:

```hcl
# terraform.tfvars (optional)
aws_region          = "us-east-1"
instance_type       = "t2.micro"
allowed_ssh_cidr    = "YOUR.IP.ADDRESS/32"  # Restrict SSH to your IP
git_repo_url        = "https://github.com/emadruga/javumbo.git"
```

## Deployment Steps

### 1. Initialize Terraform

```bash
cd terraform
terraform init
```

This downloads the required AWS provider plugins.

### 2. Plan the Deployment

```bash
terraform plan
```

Review the resources that will be created:
- VPC and networking components
- Security group with SSH, HTTP, HTTPS access
- EC2 instance with Ubuntu 22.04
- SSH key pair

### 3. Apply the Configuration

```bash
terraform apply
```

Type `yes` when prompted to confirm. This will:
- Create all AWS resources
- Launch EC2 instance
- Install Docker and Docker Compose
- Clone the repository
- Build and start Docker containers

**Note**: The deployment takes 5-10 minutes to complete after the instance starts.

### 4. Access Your Application

After `terraform apply` completes, you'll see outputs including:

```
application_url = "http://54.123.45.67"
ssh_command = "ssh -i ~/.ssh/id_rsa ubuntu@54.123.45.67"
```

**Wait 5-10 minutes** for the user data script to complete, then visit the application URL in your browser.

## Verify Deployment

### SSH into the Instance

```bash
ssh -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>
```

### Check Deployment Status

```bash
# View user data script logs
tail -f /var/log/cloud-init-output.log

# Check if deployment is complete
grep "JAVUMBO deployment complete" /var/log/cloud-init-output.log

# Check Docker containers
cd /home/ubuntu/javumbo
sudo docker compose ps

# View container logs
sudo docker compose logs

# Check individual containers
sudo docker logs flashcard_server
sudo docker logs flashcard_client
```

### Test the Application

1. Open browser to `http://<instance_public_ip>`
2. Register a new user
3. Create a deck
4. Add flashcards
5. Review cards

## Updating the Application

To update the application code:

```bash
# SSH into instance
ssh -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>

# Navigate to app directory
cd /home/ubuntu/javumbo

# Pull latest code
git pull

# Rebuild and restart containers
sudo docker compose up -d --build
```

## Destroying Resources

To remove all AWS resources created by Terraform:

```bash
terraform destroy
```

Type `yes` when prompted. This will:
- Terminate the EC2 instance
- Delete all networking components
- Remove the SSH key pair from AWS

**WARNING**: This will permanently delete all data, including user databases!

## Troubleshooting

### Instance Not Accessible

1. **Check security group**: Ensure your IP is allowed (modify `allowed_ssh_cidr`)
2. **Wait for deployment**: User data script takes 5-10 minutes
3. **Check logs**: `tail -f /var/log/cloud-init-output.log`

### Docker Containers Not Running

```bash
# SSH into instance
ssh -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>

# Check container status
cd /home/ubuntu/javumbo
sudo docker compose ps

# View logs for errors
sudo docker compose logs

# Restart containers
sudo docker compose restart
```

### Application Not Loading

1. **Verify containers are running**: `sudo docker ps`
2. **Check server logs**: `sudo docker logs flashcard_server`
3. **Check client logs**: `sudo docker logs flashcard_client`
4. **Verify port 80 is open**: `sudo netstat -tlnp | grep :80`

## Cost Estimation

- **t2.micro instance**: ~$8.50/month (free tier eligible for 12 months)
- **30 GB gp3 EBS volume**: ~$2.40/month
- **Data transfer**: Variable based on usage
- **Total**: ~$11/month (after free tier)

## Security Notes

1. **SSH Access**: Default allows SSH from anywhere (0.0.0.0/0). Change `allowed_ssh_cidr` to your IP:
   ```hcl
   allowed_ssh_cidr = "YOUR.IP.ADDRESS/32"
   ```

2. **HTTPS**: This deployment uses HTTP. For production, set up SSL/TLS with Let's Encrypt.

3. **Database Backups**: SQLite databases are on the instance. Set up regular backups to S3.

4. **SECRET_KEY**: Generated automatically. Store securely if you need to recreate the instance.

## Architecture

```
Internet
    |
    v
Security Group (SSH:22, HTTP:80, HTTPS:443)
    |
    v
EC2 Instance (Ubuntu 22.04)
    |
    +-- Docker: flashcard_server (Flask + Gunicorn, port 8000)
    |
    +-- Docker: flashcard_client (React + Nginx, port 80)
    |
    +-- SQLite DBs (/home/ubuntu/javumbo/server/)
```

## Files

- `main.tf`: Main Terraform configuration
- `variables.tf`: Input variables and defaults
- `outputs.tf`: Output values displayed after apply
- `README.md`: This file

## Next Steps

After successful deployment:

1. Set up a domain name with Route 53
2. Configure SSL/TLS with Certbot or AWS Certificate Manager
3. Set up automated backups to S3
4. Configure CloudWatch monitoring
5. Set up CI/CD for automated deployments
