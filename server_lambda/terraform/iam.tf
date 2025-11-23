# IAM Role for Lambda Function
# NOTE: Using existing LabRole from AWS Academy (cannot create IAM roles in lab environment)

# Data source to reference existing LabRole
data "aws_iam_role" "lab_role" {
  name = "LabRole"
}

# Output the role ARN for reference
output "using_lab_role" {
  description = "Using AWS Academy LabRole (has full permissions)"
  value       = data.aws_iam_role.lab_role.arn
}
