# DynamoDB Tables for Javumbo Serverless

# Users Table (replaces admin.db)
resource "aws_dynamodb_table" "users" {
  name         = var.dynamodb_users_table
  billing_mode = "PAY_PER_REQUEST" # On-demand pricing, no capacity planning needed
  hash_key     = "username"

  attribute {
    name = "username"
    type = "S"
  }

  # Enable point-in-time recovery for production
  point_in_time_recovery {
    enabled = true
  }

  # Enable encryption at rest
  server_side_encryption {
    enabled = true
  }

  tags = {
    Name        = "Javumbo Users"
    Description = "User authentication data replaces admin.db"
  }
}

# Locks Table (for distributed concurrency control)
resource "aws_dynamodb_table" "user_locks" {
  name         = var.dynamodb_locks_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "username"

  attribute {
    name = "username"
    type = "S"
  }

  # TTL for automatic lock expiration (prevents deadlocks)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  # Enable encryption at rest
  server_side_encryption {
    enabled = true
  }

  tags = {
    Name        = "Javumbo User Locks"
    Description = "Distributed locks for preventing concurrent write conflicts"
  }
}

# Sessions Table (for Lambda container session coordination)
resource "aws_dynamodb_table" "sessions" {
  name         = var.dynamodb_sessions_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "username"
    type = "S"
  }

  # TTL for automatic session cleanup (prevents stale sessions)
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  # GSI for querying sessions by username
  # Enables: "Does user X have an active session?"
  global_secondary_index {
    name            = "username-index"
    hash_key        = "username"
    projection_type = "ALL"
  }

  # Enable encryption at rest
  server_side_encryption {
    enabled = true
  }

  tags = {
    Name        = "Javumbo Sessions"
    Description = "Session coordination for Lambda instances"
  }
}
