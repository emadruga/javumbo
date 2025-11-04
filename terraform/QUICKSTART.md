# JAVUMBO Terraform Quick Start

## Prerequisites Checklist

- [ ] Terraform installed (`terraform --version`)
- [ ] AWS CLI configured (`aws configure`)
- [ ] SSH key exists at `~/.ssh/id_rsa.pub`

## Deploy in 4 Commands

```bash
# 1. Initialize Terraform
cd terraform
terraform init

# 2. Review what will be created
terraform plan

# 3. Deploy to AWS
terraform apply
# Type 'yes' when prompted

# 4. Wait 5-10 minutes, then access the URL shown in output
# Example: http://54.123.45.67
```

## After Deployment

### Check Status
```bash
# SSH into instance (use IP from terraform output)
ssh -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>

# Check deployment progress
tail -f /var/log/cloud-init-output.log

# Verify containers are running
cd /home/ubuntu/javumbo
sudo docker compose ps
```

### Access Application
Open browser to: `http://<instance_public_ip>`

## Useful Commands

### View Outputs Again
```bash
terraform output
terraform output application_url
```

### Update Application
```bash
# SSH into instance
ssh -i ~/.ssh/id_rsa ubuntu@<instance_public_ip>

# Update code and restart
cd /home/ubuntu/javumbo
git pull
sudo docker compose up -d --build
```

### Destroy Everything
```bash
terraform destroy
# Type 'yes' when prompted
# WARNING: This deletes all data!
```

## Troubleshooting

```bash
# View user data logs
tail -f /var/log/cloud-init-output.log

# Check Docker containers
sudo docker compose ps
sudo docker compose logs

# Restart containers
sudo docker compose restart
```

## Customization

Create `terraform.tfvars` to override defaults:

```hcl
aws_region       = "us-west-2"
instance_type    = "t3.small"
allowed_ssh_cidr = "1.2.3.4/32"  # Your IP only
```

## Cost

- **t2.micro**: ~$8.50/month (free tier eligible)
- **Storage**: ~$2.40/month
- **Total**: ~$11/month

Free tier: First 12 months get 750 hours/month of t2.micro for free!
