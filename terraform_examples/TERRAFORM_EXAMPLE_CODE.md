# Multi-AZ High Availability Web Application - Terraform Example

## Overview

This Terraform configuration deploys a highly available web application infrastructure on AWS, demonstrating:
- Multi-AZ deployment for fault tolerance
- Auto Scaling Group for automatic capacity management
- Elastic Load Balancer for traffic distribution
- EC2 instances serving a simple "Hello World" web page with instance metadata

## Architecture Summary

```
Internet → ELB → ASG (2-5 instances) → EC2 instances in us-east-1a & us-east-1b
```

The infrastructure spans two Availability Zones (us-east-1a and us-east-1b) to ensure high availability. If one AZ fails, the application continues running in the other AZ.

## Key Terraform Resources

### 1. **Networking (VPC, Subnets, Routes)**
- `aws_vpc.main` - Virtual Private Cloud (10.0.0.0/16)
- `aws_subnet.public_a` - Public subnet in us-east-1a (10.0.1.0/24)
- `aws_subnet.public_b` - Public subnet in us-east-1b (10.0.2.0/24)
- `aws_subnet.private` - Private subnet in us-east-1c (10.0.3.0/24)
- `aws_internet_gateway.igw` - Enables internet access
- `aws_route_table.public` - Routes traffic to internet gateway
- `aws_route_table_association.*` - Associates route tables with subnets

**Purpose:** Creates isolated network infrastructure with public internet access

### 2. **Security**
- `aws_security_group.allow_http` - Firewall rules allowing:
  - Inbound HTTP (port 80) from anywhere
  - Inbound SSH (port 22) from anywhere
  - Outbound all traffic
- `aws_key_pair.deployer` - SSH key for instance access

**Purpose:** Controls network access and enables SSH connectivity

### 3. **Compute**
- `data.aws_ami.amazon_linux_2` - Fetches latest Amazon Linux 2 AMI
- `aws_launch_configuration.app` - Template for EC2 instances:
  - Instance type: t2.micro
  - User data script: Installs Python web server, creates HTML page
  - Associates public IP addresses
- `aws_autoscaling_group.app` - Manages EC2 instance lifecycle:
  - Min: 2 instances
  - Max: 5 instances
  - Desired: 2 instances
  - Health checks via ELB
  - 5-minute grace period

**Purpose:** Defines instance configuration and automatic scaling behavior

### 4. **Load Balancing**
- `aws_elb.app` - Classic Elastic Load Balancer:
  - Distributes traffic across instances
  - Health checks on HTTP:80/
  - Cross-zone load balancing enabled
  - Spans both availability zones

**Purpose:** Distributes incoming traffic and monitors instance health

### 5. **Data Sources & Outputs**
- `data.aws_instances.app_instances` - Queries running instance details
- Outputs: ELB URL, instance IPs, SSH instructions

**Purpose:** Provides easy access to deployment information

## User Data Script

The launch configuration includes a bash script that:
1. Fetches instance metadata (Instance ID, Availability Zone)
2. Creates `/var/www/html/index.html` with a styled web page
3. Creates a systemd service for Python's built-in HTTP server
4. Starts the web server on port 80

This script runs automatically when each instance launches, making the web application immediately available.

## Resources That Impact Billing

### 💰 **Continuous Costs (Charged by Time Running)**

1. **EC2 Instances** - PRIMARY COST
   - Type: t2.micro (1 vCPU, 1 GB RAM)
   - Count: 2 instances minimum, up to 5 with auto-scaling
   - **Cost:** ~$0.0116/hour per instance
   - **Monthly estimate (2 instances):** ~$17/month
   - **Note:** Cost increases if ASG scales up to more instances

2. **Elastic Load Balancer (Classic)**
   - **Cost:** ~$0.025/hour + data transfer charges
   - **Monthly estimate:** ~$18/month base + data transfer
   - **Note:** Application Load Balancers (ALB) cost more but offer more features

3. **EBS Volumes** (Attached to EC2 Instances)
   - Default: 8 GB gp2 per instance
   - **Cost:** ~$0.10/GB-month
   - **Monthly estimate (2 instances):** ~$1.60/month

4. **Elastic IP Addresses** (if public IPs become static)
   - **Cost:** Free while attached and instance is running
   - **Note:** Current setup uses dynamic public IPs (no charge)

### 📊 **Usage-Based Costs**

5. **Data Transfer**
   - **OUT to Internet:** ~$0.09/GB after first 100 GB/month free
   - **Between AZs:** ~$0.01/GB (within same region)
   - **IN from Internet:** Free
   - **Cost varies:** Depends on traffic volume

6. **NAT Gateway** (Not used in this example)
   - Would be ~$0.045/hour + $0.045/GB processed if added
   - **Note:** Not currently deployed, but would be needed for private instances

### 🆓 **No-Cost Resources (in this configuration)**

7. **VPC, Subnets, Route Tables** - Free
8. **Security Groups** - Free
9. **Internet Gateway** - Free
10. **Auto Scaling Group** - Free (only pay for instances)
11. **Launch Configuration** - Free

## Monthly Cost Estimate

**Minimum configuration (2 t2.micro instances, low traffic):**
- EC2 Instances (2x t2.micro): ~$17/month
- ELB Classic: ~$18/month
- EBS Volumes (16 GB total): ~$1.60/month
- Data Transfer (minimal): ~$2/month
- **Total: ~$38-40/month**

**With auto-scaling to 5 instances:**
- EC2 Instances (5x t2.micro): ~$42/month
- Other costs remain similar
- **Total: ~$63-65/month**

## Cost Optimization Tips

1. **Use t2.micro (Free Tier):** First 750 hours/month free for 12 months on new AWS accounts
2. **Reserved Instances:** Save up to 75% with 1-year or 3-year commitments
3. **Spot Instances:** Save up to 90% for fault-tolerant workloads
4. **Application Load Balancer:** Consider ALB for modern features (though slightly more expensive)
5. **CloudWatch Monitoring:** Monitor traffic patterns to optimize instance count
6. **Scheduled Scaling:** Scale down during off-peak hours if traffic patterns are predictable

## Cleanup

To avoid ongoing charges, destroy all resources when done:

```bash
terraform destroy -auto-approve
```

This removes all billable resources. Always verify in AWS Console that all resources are terminated.

## Important Notes

- **Launch configurations are immutable** - Changes require creating new configuration
- **Use `name_prefix` instead of `name`** - Allows Terraform to manage lifecycle
- **User data indentation matters** - Shebang `#!/bin/bash` must be at column 0
- **Health check grace period** - Set to 5 minutes to allow instance startup
- **Instance refresh** - Required to deploy new launch configurations to existing ASG

## Links

- [AWS EC2 Pricing](https://aws.amazon.com/ec2/pricing/)
- [AWS ELB Pricing](https://aws.amazon.com/elasticloadbalancing/pricing/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
