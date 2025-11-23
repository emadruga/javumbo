# Javumbo Serverless Infrastructure - Terraform

This directory contains Terraform configuration for deploying the Javumbo serverless backend to AWS.

## Architecture Overview

- **Lambda**: Flask application wrapped with awsgi
- **API Gateway**: HTTP API (cheaper and simpler than REST API)
- **DynamoDB**: User authentication data and distributed locks
- **S3**: Per-user SQLite databases (.anki2 files)
- **CloudWatch**: Logs and monitoring

## Prerequisites

1. **AWS CLI configured**: `aws configure`
2. **Terraform installed**: `brew install terraform` (macOS) or download from terraform.io
3. **AWS Account** with appropriate permissions

## Deployment Commands

### Initial Setup (Hour 1, Day 1)

```bash
cd /Users/emadruga/proj/javumbo/server_lambda/terraform

# Initialize Terraform (downloads providers)
terraform init

# Preview what will be created
terraform plan

# Apply infrastructure (creates all resources)
terraform apply
```

When prompted, type `yes` to confirm.

### View Outputs

```bash
# Show all outputs
terraform output

# Show API Gateway URL specifically
terraform output api_gateway_url
```

### Update Infrastructure

After making changes to .tf files:

```bash
terraform plan   # Preview changes
terraform apply  # Apply changes
```

### Destroy Infrastructure

**WARNING**: This deletes ALL resources (use with caution!)

```bash
terraform destroy
```

## Files

- `main.tf`: Provider configuration and data sources
- `variables.tf`: Input variables (customize here)
- `s3.tf`: S3 bucket for user databases
- `dynamodb.tf`: DynamoDB tables (users + locks)
- `iam.tf`: IAM role and policies for Lambda
- `lambda.tf`: Lambda function definition
- `api_gateway.tf`: API Gateway HTTP API
- `outputs.tf`: Output values (URLs, ARNs, etc.)

## Cost Estimation

With AWS Free Tier (first 12 months):
- **Lambda**: 1M requests/month FREE
- **API Gateway**: 1M requests/month FREE
- **DynamoDB**: 25GB + 200M requests/month FREE
- **S3**: 5GB storage FREE

**Estimated cost for 100 users**: ~$1/month (after free tier)

## Testing Infrastructure (Hour 4, Day 1)

After `terraform apply`, run these tests:

### Test 1.1: S3 Bucket Access
```bash
# Get bucket name
BUCKET=$(terraform output -raw s3_bucket_name)

# Upload test file
echo "test" > test.anki2
aws s3 cp test.anki2 s3://$BUCKET/test/test.anki2

# Download test file
aws s3 cp s3://$BUCKET/test/test.anki2 downloaded.anki2

# Verify
diff test.anki2 downloaded.anki2

# Cleanup
aws s3 rm s3://$BUCKET/test/test.anki2
rm test.anki2 downloaded.anki2
```

### Test 1.2: DynamoDB Operations
```bash
# Get table name
TABLE=$(terraform output -raw dynamodb_users_table_name)

# Write test user
aws dynamodb put-item \
  --table-name $TABLE \
  --item '{"username":{"S":"testuser"},"user_id":{"N":"999"},"name":{"S":"Test User"}}'

# Read test user
aws dynamodb get-item \
  --table-name $TABLE \
  --key '{"username":{"S":"testuser"}}'

# Delete test user
aws dynamodb delete-item \
  --table-name $TABLE \
  --key '{"username":{"S":"testuser"}}'
```

### Test 1.3: Lambda Invocation
```bash
# Get Lambda function name
FUNCTION=$(terraform output -raw lambda_function_name)

# Invoke Lambda
aws lambda invoke \
  --function-name $FUNCTION \
  --payload '{}' \
  response.json

# Check response
cat response.json
```

### Test 1.4: API Gateway
```bash
# Get API URL
API_URL=$(terraform output -raw api_gateway_url)

# Test endpoint
curl $API_URL

# Should return: "Hello from Lambda! This is a placeholder."
```

## Next Steps

After infrastructure is deployed and tested:
- **Day 1, Hour 2**: Test Lambda can read/write S3 and DynamoDB
- **Day 2**: Implement S3SQLiteConnection context manager
- **Day 3**: Add caching
- **Day 4**: Implement conflict detection

## Troubleshooting

### "Bucket name already exists"
S3 bucket names must be globally unique. Update `s3_bucket_name` in `variables.tf`:
```hcl
variable "s3_bucket_name" {
  default = "javumbo-user-dbs-YOUR_UNIQUE_SUFFIX"
}
```

### "Access Denied"
Ensure your AWS credentials have sufficient permissions:
- S3: CreateBucket, PutObject, GetObject
- DynamoDB: CreateTable, PutItem, GetItem
- Lambda: CreateFunction
- IAM: CreateRole, AttachRolePolicy
- API Gateway: CreateApi

### Lambda timeout errors
Increase timeout in `variables.tf`:
```hcl
variable "lambda_timeout" {
  default = 60  # seconds
}
```

## State Management

Terraform stores state in `terraform.tfstate` (gitignored). For production, consider using remote state (S3 + DynamoDB for locking).

## Security Notes

- ⚠️ `SECRET_KEY` is hardcoded in Lambda environment variables. For production, use AWS Secrets Manager.
- ⚠️ CORS is set to `*` (allow all origins). Restrict to your frontend domain in production.
- ✅ S3 bucket has public access blocked
- ✅ S3 bucket has versioning enabled
- ✅ DynamoDB has point-in-time recovery enabled
- ✅ All data encrypted at rest

## Contact

For issues with infrastructure deployment, check:
1. CloudWatch Logs: `/aws/lambda/javumbo-api`
2. AWS Console: Lambda, API Gateway, S3, DynamoDB
3. Terraform docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
