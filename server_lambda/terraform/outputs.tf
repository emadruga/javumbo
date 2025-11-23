# Terraform Outputs - Important values to reference after deployment

output "s3_bucket_name" {
  description = "Name of the S3 bucket for user databases"
  value       = aws_s3_bucket.user_dbs.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.user_dbs.arn
}

output "dynamodb_users_table_name" {
  description = "Name of the DynamoDB users table"
  value       = aws_dynamodb_table.users.name
}

output "dynamodb_locks_table_name" {
  description = "Name of the DynamoDB locks table"
  value       = aws_dynamodb_table.user_locks.name
}

output "dynamodb_sessions_table_name" {
  description = "Name of the DynamoDB sessions table"
  value       = aws_dynamodb_table.sessions.name
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.api.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.api.arn
}

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = data.aws_iam_role.lab_role.arn
}

output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.http_api.api_endpoint
}

output "api_gateway_id" {
  description = "API Gateway ID"
  value       = aws_apigatewayv2_api.http_api.id
}

# Summary output for quick reference
output "deployment_summary" {
  description = "Summary of deployed resources"
  value = {
    api_url                 = aws_apigatewayv2_api.http_api.api_endpoint
    lambda_function         = aws_lambda_function.api.function_name
    s3_bucket               = aws_s3_bucket.user_dbs.id
    dynamodb_users_table    = aws_dynamodb_table.users.name
    dynamodb_locks_table    = aws_dynamodb_table.user_locks.name
    dynamodb_sessions_table = aws_dynamodb_table.sessions.name
    region                  = data.aws_region.current.name
    account_id              = data.aws_caller_identity.current.account_id
  }
}
