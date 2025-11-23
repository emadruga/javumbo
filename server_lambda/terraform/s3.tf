# S3 Bucket for User Databases (.anki2 files)

resource "aws_s3_bucket" "user_dbs" {
  bucket = "${var.s3_bucket_name}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "Javumbo User Databases"
    Description = "Stores per-user .anki2 SQLite files"
  }
}

# Enable versioning for data protection
resource "aws_s3_bucket_versioning" "user_dbs" {
  bucket = aws_s3_bucket.user_dbs.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Block public access (security best practice)
resource "aws_s3_bucket_public_access_block" "user_dbs" {
  bucket = aws_s3_bucket.user_dbs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "user_dbs" {
  bucket = aws_s3_bucket.user_dbs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle rule to manage old versions (optional, cost optimization)
resource "aws_s3_bucket_lifecycle_configuration" "user_dbs" {
  bucket = aws_s3_bucket.user_dbs.id

  rule {
    id     = "delete-old-versions"
    status = "Enabled"

    filter {} # Empty filter applies to all objects

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}
