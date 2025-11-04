# JAVUMBO AWS Terraform Deployment Plan - Simple Single Instance

This document outlines the Terraform infrastructure plan for deploying the JAVUMBO flashcard application to AWS using a simple, single EC2 instance architecture.

## Deployment Overview

**Target Environment**: AWS EC2 (Ubuntu 22.04)
**Architecture**: Single-instance Docker-based deployment
**Deployment Method**: Docker Compose (server + client containers)
**Reference Documents**:
- Base Terraform example: `terraform_examples/main.tf`
- Production deployment guide: `docs/PRODUCTION.md` (Section 6: Docker Deployment)
- Existing Docker setup: `docker-compose.yml`, `server/Dockerfile`, `client/Dockerfile`

---

## Infrastructure Components

### 1. Networking

#### VPC Configuration
- **VPC**: Single VPC with CIDR block `10.0.0.0/16`
- **Subnets**:
  - Public subnet in a single availability zone (e.g., `us-east-1a`)
  - CIDR: `10.0.1.0/24`
- **Internet Gateway**: For public internet access
- **Route Table**: Public route table with route to internet gateway (0.0.0.0/0)

#### Security Group
- **Name**: `javumbo-sg`
- **Ingress Rules**:
  - SSH (port 22): From 0.0.0.0/0 (or restricted to specific IP for better security)
  - HTTP (port 80): From 0.0.0.0/0
  - HTTPS (port 443): From 0.0.0.0/0 (for future SSL setup)
- **Egress Rules**:
  - All traffic: To 0.0.0.0/0 (allow outbound for package installation)

### 2. Compute

#### EC2 Instance
- **AMI**: Latest Ubuntu 22.04 LTS (using data source to fetch dynamically)
- **Instance Type**: `t2.micro` (or `t3.micro` for better performance)
- **Key Pair**: SSH key for remote access
- **Public IP**: Enable automatic public IP assignment
- **Root Volume**: 20-30 GB gp3 (sufficient for OS, application, and databases)

#### SSH Key Management
- **Key Pair Resource**: Reference existing SSH public key from local system
- **Default Path**: `~/.ssh/id_rsa.pub` (or configurable via variable)
- **Alternative**: Generate new key pair specifically for this deployment

### 3. User Data Script (Docker-Based Deployment)

The EC2 instance will be provisioned with a `user_data` script that performs:

1. **System Updates**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Install Docker and Docker Compose**
   ```bash
   # Install Docker
   sudo apt install -y docker.io

   # Install Docker Compose V2
   sudo apt install -y docker-compose-v2

   # Add ubuntu user to docker group (allows running docker without sudo)
   sudo usermod -aG docker ubuntu
   ```

3. **Clone Repository**
   ```bash
   cd /home/ubuntu
   git clone https://github.com/your-username/javumbo.git
   cd javumbo
   ```

4. **Configure Environment**
   - Generate SECRET_KEY and create `server/.env` file:
   ```bash
   cd /home/ubuntu/javumbo
   SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(24))')
   echo "SECRET_KEY='${SECRET_KEY}'" > server/.env
   ```

5. **Build and Start Docker Containers**
   ```bash
   cd /home/ubuntu/javumbo
   sudo docker compose build
   sudo docker compose up -d
   ```

6. **Service Verification**
   - Check container status: `sudo docker compose ps`
   - View logs: `sudo docker compose logs -f`
   - Verify HTTP access on port 80

**Key Benefits of Docker Approach**:
- **Faster Deployment**: No manual dependency installation or configuration
- **Consistency**: Identical environment across dev/prod
- **Isolation**: Containers are self-contained with all dependencies
- **Simplified Management**: Single command to start/stop entire stack
- **Easy Updates**: `git pull && docker compose up -d --build`

---

## Terraform Resources Required

### Core Resources

1. **Provider Configuration**
   - AWS provider with region (default: `us-east-1`)

2. **Data Sources**
   - `aws_ami`: Fetch latest Ubuntu 22.04 AMI
   - Filter for: `ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*`

3. **Networking Resources**
   - `aws_vpc`
   - `aws_subnet` (public)
   - `aws_internet_gateway`
   - `aws_route_table`
   - `aws_route_table_association`
   - `aws_security_group` with rules

4. **Compute Resources**
   - `aws_key_pair`
   - `aws_instance` with user_data script

### Variables (Optional for v1)

```hcl
variable "region" {
  default = "us-east-1"
}

variable "instance_type" {
  default = "t2.micro"
}

variable "ssh_public_key_path" {
  default = "~/.ssh/id_rsa.pub"
}

variable "allowed_ssh_cidr" {
  default = "0.0.0.0/0"  # Restrict this in production!
}

variable "project_name" {
  default = "javumbo"
}
```

---

## Terraform Outputs

The following outputs will be displayed after `terraform apply`:

### 1. Public IP Address
```hcl
output "instance_public_ip" {
  value       = aws_instance.javumbo.public_ip
  description = "Public IP address of the JAVUMBO instance"
}
```

### 2. Application URL
```hcl
output "application_url" {
  value       = "http://${aws_instance.javumbo.public_ip}"
  description = "URL to access the JAVUMBO application"
}
```

### 3. SSH Connection Command
```hcl
output "ssh_command" {
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_instance.javumbo.public_ip}"
  description = "SSH command to connect to the instance"
}
```

### 4. Instance ID
```hcl
output "instance_id" {
  value       = aws_instance.javumbo.id
  description = "EC2 instance ID"
}
```

### 5. Log Locations (Documentation)
```hcl
output "log_locations" {
  value = <<-EOT
    Application logs can be found at:
    - Docker Compose logs: cd /home/ubuntu/javumbo && sudo docker compose logs -f
    - Container status: cd /home/ubuntu/javumbo && sudo docker compose ps
    - User Data Script: /var/log/cloud-init-output.log
    - Individual container logs:
      - Server: sudo docker logs flashcard_server
      - Client: sudo docker logs flashcard_client
  EOT
  description = "Log file locations for troubleshooting"
}
```

---

## Implementation Phases

### Phase 1: Basic Infrastructure
- VPC, subnet, internet gateway, route table
- Security group with SSH and HTTP access
- EC2 instance with Ubuntu 22.04
- SSH key pair
- Basic outputs (IP, SSH command)

### Phase 2: Application Deployment (Docker)
- User data script for Docker installation
- Docker Compose installation
- Repository cloning
- SECRET_KEY generation
- Docker image building (server + client)
- Container startup via docker-compose

### Phase 3: Testing & Validation
- Verify instance provisioning
- Test SSH access
- Verify application is running (HTTP access)
- Check service status via SSH
- Review logs for errors

### Phase 4: Documentation & Refinement
- Document any manual steps required
- Add troubleshooting notes
- Consider security improvements (restrict SSH CIDR)
- Plan for future enhancements (SSL, monitoring, backups)

---

## Why Docker for This Deployment?

### Advantages Over Traditional Deployment

1. **Simplified User Data Script**
   - Traditional: ~100+ lines installing Python, Node.js, npm, nginx, configuring systemd, etc.
   - Docker: ~20 lines installing Docker + running `docker compose up`

2. **Faster Deployment**
   - No manual dependency installation and configuration
   - Pre-built images can be cached and reused
   - Single command deploys entire stack

3. **Consistency & Reproducibility**
   - Identical environment across dev/staging/production
   - "Works on my machine" problem eliminated
   - Dockerfiles serve as executable documentation

4. **Easier Maintenance & Updates**
   - Update code: `git pull && docker compose up -d --build`
   - Rollback: Keep previous images and switch back
   - No concern about system-level dependency conflicts

5. **Isolation & Security**
   - Application dependencies isolated from host system
   - Easier to implement resource limits
   - Cleaner host system

6. **Existing Setup**
   - Docker configuration already exists and tested
   - Dockerfiles in `server/` and `client/` directories
   - `docker-compose.yml` at project root
   - Leveraging existing work vs. creating new systemd services

---

## Docker Architecture Details

The deployment uses the existing Docker Compose configuration with two containers:

### Server Container (`flashcard_server`)
- **Base Image**: Python 3.10-slim
- **Functionality**: Flask backend with Gunicorn WSGI server
- **Port**: 8000 (internal, exposed only to client container)
- **Volume Mount**: `./server:/app` (provides access to databases on host)
- **Environment**: Loads `server/.env` for SECRET_KEY
- **Databases**: SQLite files (`admin.db`, `user_dbs/*.anki2`) persist on host

### Client Container (`flashcard_client`)
- **Base Image**: Multi-stage build (Node.js LTS Alpine + Nginx stable Alpine)
- **Build Stage 1**: Compiles React application with Vite
- **Build Stage 2**: Serves static files via Nginx
- **Port**: 80 (mapped to host port 80)
- **Nginx Config**: Reverse proxies API calls to server container
- **Dependencies**: Depends on server container

### Networking
- **Bridge Network**: `flashcard-net` connects both containers
- **Internal Communication**: Client Nginx proxies to `http://server:8000`
- **External Access**: Only port 80 exposed to public internet

### Data Persistence
- Server volume mount ensures databases persist across container restarts
- No separate database container needed (SQLite is file-based)
- Easy backups: Simply backup `/home/ubuntu/javumbo/server/` directory

---

## Known Considerations

### Application-Specific Requirements

1. **SECRET_KEY Generation**
   - User data script should generate a secure random key
   - Alternative: Use AWS Secrets Manager or SSM Parameter Store

2. **Database Initialization**
   - Admin database (`admin.db`) creation
   - Proper file permissions for SQLite databases
   - Directory permissions for `user_dbs/`

3. **Frontend Build Configuration**
   - The client Dockerfile handles the build automatically
   - Environment variables are baked into the build at container build time
   - Default configuration in repository should work for Docker deployment
   - Nginx config in `client/nginx.conf` handles proxy routing

4. **Repository Access**
   - If repository is private, need to handle authentication
   - Consider: SSH keys, deploy tokens, or public repository

### Deployment Timing

- User data script execution can take 5-10 minutes
- Docker image building includes:
  - Server: Python dependencies installation
  - Client: npm install + React build (multi-stage)
- First build takes longer, subsequent rebuilds are cached
- Need to wait for cloud-init completion before testing
- Check: `/var/log/cloud-init-output.log` for progress

### Security Considerations

1. **Immediate**:
   - Use security groups, not open 0.0.0.0/0 for SSH in production
   - Consider VPN or bastion host for SSH access

2. **Future**:
   - Enable HTTPS with Let's Encrypt/Certbot
   - Use AWS Certificate Manager + Application Load Balancer
   - Implement database backups to S3
   - Use IAM roles instead of hardcoded credentials
   - Enable CloudWatch monitoring and logs

---

## Testing Checklist

After `terraform apply` completes:

- [ ] Note the `instance_public_ip` from outputs
- [ ] Wait 5-10 minutes for user data script completion
- [ ] SSH into instance: `ssh -i ~/.ssh/id_rsa ubuntu@<IP>`
- [ ] Check cloud-init completion: `tail -f /var/log/cloud-init-output.log`
- [ ] Verify Docker containers: `cd /home/ubuntu/javumbo && sudo docker compose ps`
- [ ] Check container logs: `sudo docker compose logs`
- [ ] Verify both containers are running:
  - `sudo docker ps` should show `flashcard_server` and `flashcard_client`
- [ ] Test application: Open `http://<instance_public_ip>` in browser
- [ ] Test user registration and login
- [ ] Check for errors in Docker logs

---

## Future Enhancements

1. **High Availability**
   - Auto Scaling Group with multiple instances
   - Application Load Balancer
   - Multi-AZ deployment
   - RDS for shared database (migrate from SQLite)

2. **Monitoring & Logging**
   - CloudWatch metrics and alarms
   - Centralized logging
   - Application performance monitoring

3. **Security**
   - SSL/TLS certificates
   - WAF (Web Application Firewall)
   - Secrets management
   - Regular security updates automation

4. **CI/CD**
   - Automated deployments via GitHub Actions
   - Blue-green deployments
   - Automated testing

5. **Backup & Recovery**
   - Automated database backups to S3
   - AMI snapshots
   - Disaster recovery procedures

---

## Next Steps

1. Create `main.tf` based on this plan
2. Create `variables.tf` for configurable parameters
3. Create `outputs.tf` for the outputs defined above
4. Write comprehensive user data script
5. Test in development AWS account
6. Document any manual steps or issues encountered
7. Iterate and refine
