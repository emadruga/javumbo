#!/bin/bash
set -e

echo "🚀 Javumbo Serverless Deployment Script"
echo "========================================"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI not installed. Please install from https://aws.amazon.com/cli/"; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo "❌ Terraform not installed. Please install from https://www.terraform.io/downloads"; exit 1; }
echo "✅ AWS CLI and Terraform found"
echo ""

# Check AWS credentials
aws sts get-caller-identity >/dev/null 2>&1 || { echo "❌ AWS credentials not configured. Run 'aws configure'"; exit 1; }
echo "✅ AWS credentials configured"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "   Account: $ACCOUNT_ID"
echo ""

# Check if package exists
if [ ! -f "lambda_deployment.zip" ]; then
    echo "❌ lambda_deployment.zip not found!"
    echo ""
    echo "Please download it from one of these sources:"
    echo "  • GitHub Releases: https://github.com/emadruga/javumbo/releases"
    echo "  • Instructor-provided shared folder"
    echo ""
    echo "Or rebuild it using Docker:"
    echo "  ./build_lambda_package.sh"
    echo ""
    exit 1
fi

# Verify package structure
echo "✅ Verifying lambda_deployment.zip structure..."
unzip -l lambda_deployment.zip | grep -q "app.py" || { echo "❌ Invalid package: app.py not found at root"; exit 1; }
unzip -l lambda_deployment.zip | grep -q "lambda_handler.py" || { echo "❌ Invalid package: lambda_handler.py not found"; exit 1; }
unzip -l lambda_deployment.zip | grep -q "bcrypt/_bcrypt.abi3.so" || { echo "❌ Invalid package: bcrypt not found (might be macOS binary!)"; exit 1; }
PACKAGE_SIZE=$(ls -lh lambda_deployment.zip | awk '{print $5}')
echo "   Package size: $PACKAGE_SIZE"
echo ""

# Deploy infrastructure
echo "📦 Deploying infrastructure with Terraform..."
cd terraform

# Initialize Terraform
terraform init -upgrade

# Show plan
echo ""
echo "📋 Terraform will create the following resources:"
terraform plan -no-color | grep -E "(will be created|Plan:)" || true
echo ""

# Confirm deployment
read -p "Continue with deployment? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Deployment cancelled"
    exit 1
fi

# Apply Terraform
terraform apply -auto-approve

# Get API Gateway endpoint
API_ENDPOINT=$(terraform output -raw api_endpoint 2>/dev/null || echo "")
if [ -z "$API_ENDPOINT" ]; then
    echo "❌ Failed to get API Gateway endpoint from Terraform outputs"
    exit 1
fi

echo ""
echo "✅ Infrastructure deployed successfully"
echo "   API Endpoint: $API_ENDPOINT"
echo ""

# Deploy Lambda code
echo "🔧 Deploying Lambda function code..."
cd ..
aws lambda update-function-code \
  --function-name javumbo-api \
  --zip-file fileb://lambda_deployment.zip \
  --region us-east-1 \
  --query '{FunctionName: FunctionName, LastModified: LastModified, CodeSize: CodeSize}' \
  --output table

echo ""
echo "✅ Lambda code deployed"
echo ""

# Wait for deployment to propagate
echo "⏳ Waiting for deployment to propagate (10 seconds)..."
sleep 10

# Deploy Frontend to S3
echo "🎨 Deploying frontend to S3..."
cd terraform

# Get S3 frontend bucket name from Terraform outputs
S3_FRONTEND_BUCKET=$(terraform output -raw s3_frontend_bucket_name 2>/dev/null || echo "")
if [ -z "$S3_FRONTEND_BUCKET" ]; then
    echo "❌ Failed to get S3 frontend bucket name from Terraform outputs"
    exit 1
fi

cd ../../client_lambda

# Update .env.production with current API endpoint
echo "📝 Updating frontend configuration with API endpoint..."
cat > .env.production <<EOF
# Production environment variables
# Points to deployed API Gateway
VITE_API_BASE_URL=${API_ENDPOINT}/api
VITE_APP_BASE_PATH=/
EOF

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install Node.js and npm"
    exit 1
fi

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# Build frontend
echo "🔨 Building frontend..."
npm run build

# Upload to S3
echo "☁️  Uploading frontend to S3 bucket: ${S3_FRONTEND_BUCKET}..."
aws s3 sync dist/ s3://${S3_FRONTEND_BUCKET}/ --delete --region us-east-1

echo ""
echo "✅ Frontend deployed to S3"
echo ""

cd ../server_lambda

# Test deployment
echo "🧪 Testing deployment..."
echo "   Testing: ${API_ENDPOINT}/api/health"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${API_ENDPOINT}/api/health")

echo ""
if [ "$HTTP_CODE" -eq 401 ]; then
    echo "✅ ✅ ✅ DEPLOYMENT SUCCESSFUL! ✅ ✅ ✅"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 Your Javumbo application is live!"
    echo ""
    echo "   Frontend (Web App): ${API_ENDPOINT}"
    echo "   API Endpoint:       ${API_ENDPOINT}/api"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📖 Quick Start:"
    echo ""
    echo "🌐 Access the web application:"
    echo "   Open in browser: ${API_ENDPOINT}"
    echo ""
    echo "🔧 Or test the API directly:"
    echo ""
    echo "1. Test health endpoint:"
    echo "   curl ${API_ENDPOINT}/api/health"
    echo ""
    echo "2. Register a user:"
    echo "   curl -X POST ${API_ENDPOINT}/api/register \\"
    echo "     -H \"Content-Type: application/json\" \\"
    echo "     -d '{\"username\":\"student1\",\"name\":\"Student One\",\"password\":\"password123456\"}'"
    echo ""
    echo "3. Login:"
    echo "   curl -X POST ${API_ENDPOINT}/api/login \\"
    echo "     -H \"Content-Type: application/json\" \\"
    echo "     -d '{\"username\":\"student1\",\"password\":\"password123456\"}'"
    echo ""
    echo "4. Get JWT token from login response and use it:"
    echo "   TOKEN=\"your_jwt_token_here\""
    echo "   curl -X GET ${API_ENDPOINT}/api/decks \\"
    echo "     -H \"Authorization: Bearer \$TOKEN\""
    echo ""
    echo "💡 Note: The frontend is automatically configured to use this API endpoint"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📚 Documentation:"
    echo "   • API Docs: docs/REST_API.md"
    echo "   • Architecture: docs/REFACTOR_WEEK_4.md"
    echo "   • Testing Guide: docs/TESTING_THE_API_IN_AWS_LAMBDA.md"
    echo ""
    echo "🧹 To clean up (destroy all resources):"
    echo "   cd terraform && terraform destroy"
    echo ""
elif [ "$HTTP_CODE" -eq 404 ]; then
    echo "⚠️  DEPLOYMENT COMPLETED BUT VERIFICATION FAILED"
    echo "   HTTP 404: API Gateway routes may not be configured correctly"
    echo ""
    echo "Try testing directly:"
    echo "   curl ${API_ENDPOINT}/"
    echo ""
    echo "Check API Gateway integration:"
    echo "   aws apigatewayv2 get-routes --api-id \$(echo ${API_ENDPOINT} | cut -d'/' -f3 | cut -d'.' -f1) --region us-east-1"
elif [ "$HTTP_CODE" -eq 500 ]; then
    echo "❌ DEPLOYMENT VERIFICATION FAILED (HTTP 500)"
    echo "   Lambda function is crashing on invocation"
    echo ""
    echo "Check CloudWatch logs for errors:"
    echo "   aws logs tail /aws/lambda/javumbo-api --since 5m --follow"
    echo ""
    echo "Common causes:"
    echo "   • Wrong Lambda package (macOS binaries instead of Linux)"
    echo "   • Missing dependencies in package"
    echo "   • Runtime errors in application code"
else
    echo "❌ DEPLOYMENT VERIFICATION FAILED (HTTP $HTTP_CODE)"
    echo ""
    echo "Check API Gateway status:"
    echo "   aws apigatewayv2 get-apis --query 'Items[?Name==\`javumbo-api\`]' --region us-east-1"
    echo ""
    echo "Check Lambda function:"
    echo "   aws lambda get-function-configuration --function-name javumbo-api --region us-east-1"
    echo ""
    echo "Check CloudWatch logs:"
    echo "   aws logs tail /aws/lambda/javumbo-api --since 5m --follow"
fi

echo ""
echo "Done! 🎓"
