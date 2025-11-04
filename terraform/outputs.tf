output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.javumbo.id
}

output "instance_public_ip" {
  description = "Public IP address of the JAVUMBO instance"
  value       = aws_instance.javumbo.public_ip
}

output "application_url" {
  description = "URL to access the JAVUMBO application"
  value       = "http://${aws_instance.javumbo.public_ip}"
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_instance.javumbo.public_ip}"
}

output "log_locations" {
  description = "Log file locations for troubleshooting"
  value       = <<-EOT
    Application logs can be found at:
    - Docker Compose logs: cd /home/ubuntu/javumbo && sudo docker compose logs -f
    - Container status: cd /home/ubuntu/javumbo && sudo docker compose ps
    - User Data Script: /var/log/cloud-init-output.log
    - Individual container logs:
      - Server: sudo docker logs flashcard_server
      - Client: sudo docker logs flashcard_client
  EOT
}

output "deployment_info" {
  description = "Deployment information"
  value       = <<-EOT
    JAVUMBO Deployment Summary
    ==========================
    Instance ID: ${aws_instance.javumbo.id}
    Public IP: ${aws_instance.javumbo.public_ip}
    Application URL: http://${aws_instance.javumbo.public_ip}

    SSH Access:
    ssh -i ~/.ssh/id_rsa ubuntu@${aws_instance.javumbo.public_ip}

    Note: Wait 5-10 minutes for deployment to complete.
    Check deployment status: tail -f /var/log/cloud-init-output.log
  EOT
}
