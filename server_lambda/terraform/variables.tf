# Variables for JAVUMBO Serverless Infrastructure

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "javumbo"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for user databases (must be globally unique)"
  type        = string
  default     = "javumbo-user-dbs"
}

variable "dynamodb_users_table" {
  description = "DynamoDB table name for user authentication"
  type        = string
  default     = "javumbo-users"
}

variable "dynamodb_locks_table" {
  description = "DynamoDB table name for distributed locks"
  type        = string
  default     = "javumbo-user-locks"
}

variable "dynamodb_sessions_table" {
  description = "DynamoDB table name for session management"
  type        = string
  default     = "javumbo-sessions"
}

variable "lambda_function_name" {
  description = "Lambda function name"
  type        = string
  default     = "javumbo-api"
}

variable "lambda_memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 512
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_ephemeral_storage" {
  description = "Lambda ephemeral storage in MB"
  type        = number
  default     = 2048
}
