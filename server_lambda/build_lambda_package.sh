#!/bin/bash
set -e

echo "🔨 Building Lambda Deployment Package"
echo "======================================"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not installed. Please install Docker Desktop"; exit 1; }
docker ps >/dev/null 2>&1 || { echo "❌ Docker daemon not running. Please start Docker Desktop"; exit 1; }
echo "✅ Docker is running"
echo ""

# Clean old artifacts
echo "🧹 Cleaning old artifacts..."
rm -rf package
rm -f lambda_deployment.zip
echo "✅ Cleaned package/ and lambda_deployment.zip"
echo ""

# Install dependencies using Docker (Linux x86_64 binaries)
echo "📦 Installing dependencies with Docker..."
echo "   This ensures Linux binaries for AWS Lambda"
echo ""
docker run --rm --platform linux/amd64 \
  --entrypoint pip \
  -v "$(pwd)":/var/task \
  public.ecr.aws/lambda/python:3.11 \
  install -r /var/task/requirements.txt -t /var/task/package/ --upgrade

echo ""
echo "✅ Dependencies installed"
echo ""

# Package dependencies
echo "📦 Creating deployment package..."
cd package
zip -r9 ../lambda_deployment.zip . -x "*.pyc" -x "*__pycache__*" -q
cd ..
echo "✅ Dependencies packaged"

# Add application code at root level
echo "📝 Adding application code..."
cd src
zip -g ../lambda_deployment.zip *.py -q
cd ..
echo "✅ Application code added"
echo ""

# Verify package structure
echo "🔍 Verifying package structure..."
echo ""
echo "Checking critical files:"

# Check app.py
if unzip -l lambda_deployment.zip | grep -q "^\s*[0-9]*\s.*app\.py$"; then
    APP_SIZE=$(unzip -l lambda_deployment.zip | grep "app\.py$" | awk '{print $1}')
    echo "  ✅ app.py found (${APP_SIZE} bytes)"
else
    echo "  ❌ app.py NOT found at root level!"
    exit 1
fi

# Check lambda_handler.py
if unzip -l lambda_deployment.zip | grep -q "^\s*[0-9]*\s.*lambda_handler\.py$"; then
    echo "  ✅ lambda_handler.py found"
else
    echo "  ❌ lambda_handler.py NOT found at root level!"
    exit 1
fi

# Check bcrypt binary (CRITICAL - must be Linux binary)
if unzip -l lambda_deployment.zip | grep -q "bcrypt/_bcrypt\.abi3\.so"; then
    BCRYPT_SIZE=$(unzip -l lambda_deployment.zip | grep "bcrypt/_bcrypt\.abi3\.so" | awk '{print $1}')
    if [ "$BCRYPT_SIZE" -gt 600000 ]; then
        echo "  ✅ bcrypt/_bcrypt.abi3.so found (Linux binary, ${BCRYPT_SIZE} bytes)"
    else
        echo "  ⚠️  bcrypt binary found but size suspicious (${BCRYPT_SIZE} bytes)"
        echo "      Expected: ~631,000 bytes for Linux x86_64"
    fi
else
    echo "  ❌ bcrypt/_bcrypt.abi3.so NOT found!"
    echo "      This will cause 'invalid ELF header' errors in Lambda"
    exit 1
fi

# Package summary
PACKAGE_SIZE=$(ls -lh lambda_deployment.zip | awk '{print $5}')
FILE_COUNT=$(unzip -l lambda_deployment.zip | tail -1 | awk '{print $2}')
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ✅ ✅ PACKAGE BUILD SUCCESSFUL! ✅ ✅ ✅"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 Package Details:"
echo "   File: lambda_deployment.zip"
echo "   Size: $PACKAGE_SIZE"
echo "   Files: $FILE_COUNT"
echo ""
echo "📚 Key Components:"
unzip -l lambda_deployment.zip | grep -E "(app\.py|lambda_handler\.py|bcrypt/_bcrypt|flask/|boto3/)" | head -10
echo "   ..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "1. Deploy to AWS Lambda:"
echo "   ./deploy.sh"
echo ""
echo "2. Or deploy manually:"
echo "   cd terraform && terraform apply"
echo "   aws lambda update-function-code \\"
echo "     --function-name javumbo-api \\"
echo "     --zip-file fileb://../lambda_deployment.zip \\"
echo "     --region us-east-1"
echo ""
echo "3. Or save for later use:"
echo "   cp lambda_deployment.zip ~/backups/lambda_deployment_\$(date +%Y%m%d).zip"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Done! 🎉"
