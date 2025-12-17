# Lambda Function (placeholder - will be updated with actual code later)

# Create a placeholder Lambda deployment package
data "archive_file" "lambda_placeholder" {
  type        = "zip"
  output_path = "${path.module}/lambda_placeholder.zip"

  source {
    content  = <<-EOT
      def handler(event, context):
          return {
              'statusCode': 200,
              'body': 'Hello from Lambda! This is a placeholder.'
          }
    EOT
    filename = "lambda_function.py"
  }
}

# Lambda function
resource "aws_lambda_function" "api" {
  filename         = data.archive_file.lambda_placeholder.output_path
  function_name    = var.lambda_function_name
  role             = data.aws_iam_role.lab_role.arn
  handler          = "lambda_handler.handler"
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256
  runtime          = "python3.11"

  memory_size = var.lambda_memory_size
  timeout     = var.lambda_timeout

  ephemeral_storage {
    size = var.lambda_ephemeral_storage # 2 GB for caching user databases
  }

  environment {
    variables = {
      S3_BUCKET               = aws_s3_bucket.user_dbs.id
      S3_FRONTEND_BUCKET      = aws_s3_bucket.frontend.id
      DYNAMODB_USERS_TABLE    = aws_dynamodb_table.users.name
      DYNAMODB_LOCKS_TABLE    = aws_dynamodb_table.user_locks.name
      DYNAMODB_SESSIONS_TABLE = aws_dynamodb_table.sessions.name
      SESSION_TTL             = "300"  # 5 minutes in seconds
      DB_CACHE_TTL            = "300"  # 5 minutes in seconds
      SECRET_KEY              = "CHANGE_THIS_IN_PRODUCTION" # TODO: Use AWS Secrets Manager
      # Note: AWS_LAMBDA_FUNCTION_NAME is automatically set by AWS Lambda runtime
    }
  }

  tags = {
    Name        = "Javumbo API"
    Description = "Main API Lambda function for Javumbo serverless backend"
  }

  # Lifecycle to ignore changes to source code hash (we'll update manually/via CI/CD)
  lifecycle {
    ignore_changes = [
      source_code_hash,
      filename
    ]
  }
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 7 # Reduce to 7 days for dev, increase for prod

  tags = {
    Name = "Javumbo Lambda Logs"
  }
}
