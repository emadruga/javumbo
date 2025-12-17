#!/usr/bin/env python3
"""
Comprehensive backup script for Javumbo AWS deployment.
Backs up Lambda package, Terraform state, and DynamoDB data.
"""

import boto3
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

def create_backup_directory():
    """Create timestamped backup directory."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(f'deployments/backup_{timestamp}')
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir

def backup_lambda_package(backup_dir):
    """Backup Lambda deployment package."""
    print("📦 Backing up Lambda deployment package...")

    # Check for lambda package in different locations
    lambda_files = [
        'lambda_deployment.zip',
        'deployments/lambda_deployment-20251217.zip'
    ]

    source = None
    for f in lambda_files:
        if Path(f).exists():
            source = Path(f)
            break

    if source:
        dest = backup_dir / 'lambda_deployment.zip'
        shutil.copy2(source, dest)
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"   ✅ Lambda package backed up ({size_mb:.1f} MB)")
        return True
    else:
        print(f"   ⚠️  Lambda package not found (will need to rebuild)")
        return False

def backup_terraform_state(backup_dir):
    """Backup Terraform state files."""
    print("🏗️  Backing up Terraform state...")

    terraform_dir = Path('terraform')
    state_files = ['terraform.tfstate', 'terraform.tfstate.backup']

    backed_up = 0
    for state_file in state_files:
        source = terraform_dir / state_file
        if source.exists():
            dest = backup_dir / state_file
            shutil.copy2(source, dest)
            backed_up += 1

    if backed_up > 0:
        print(f"   ✅ Terraform state backed up ({backed_up} files)")
        return True
    else:
        print(f"   ⚠️  No Terraform state found")
        return False

def backup_dynamodb_table(backup_dir, table_name):
    """Backup a single DynamoDB table."""
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')

    try:
        print(f"   Scanning table: {table_name}")

        # Scan the entire table
        items = []
        response = dynamodb.scan(TableName=table_name)
        items.extend(response.get('Items', []))

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = dynamodb.scan(
                TableName=table_name,
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        # Save to file
        output_file = backup_dir / f'{table_name}_backup.json'
        with open(output_file, 'w') as f:
            json.dump({
                'table_name': table_name,
                'item_count': len(items),
                'items': items,
                'backup_timestamp': datetime.now().isoformat()
            }, f, indent=2)

        print(f"   ✅ Backed up {len(items)} items from {table_name}")
        return True

    except dynamodb.exceptions.ResourceNotFoundException:
        print(f"   ⚠️  Table {table_name} does not exist")
        return False
    except Exception as e:
        print(f"   ❌ Error backing up {table_name}: {e}")
        return False

def backup_dynamodb_data(backup_dir):
    """Backup all DynamoDB tables."""
    print("💾 Backing up DynamoDB tables...")

    tables = [
        'javumbo-users',
        'javumbo-sessions',
        'javumbo-user-locks'
    ]

    backed_up = 0
    for table in tables:
        if backup_dynamodb_table(backup_dir, table):
            backed_up += 1

    return backed_up > 0

def backup_s3_user_databases(backup_dir):
    """Backup user database files from S3."""
    print("🗄️  Backing up user databases from S3...")

    s3 = boto3.client('s3', region_name='us-east-1')

    try:
        # Get account ID to construct bucket name
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        bucket_name = f'javumbo-user-dbs-{account_id}'

        # List all objects in bucket
        response = s3.list_objects_v2(Bucket=bucket_name)

        if 'Contents' not in response:
            print(f"   ⚠️  No user databases found in S3")
            return False

        # Create subdirectory for user databases
        db_dir = backup_dir / 'user_databases'
        db_dir.mkdir(exist_ok=True)

        # Download each database file
        file_count = 0
        for obj in response['Contents']:
            key = obj['Key']
            local_file = db_dir / key.replace('/', '_')
            s3.download_file(bucket_name, key, str(local_file))
            file_count += 1

        print(f"   ✅ Backed up {file_count} user database files")
        return True

    except Exception as e:
        print(f"   ⚠️  Could not backup user databases: {e}")
        return False

def create_readme(backup_dir):
    """Create README file documenting the backup."""
    print("📝 Creating backup documentation...")

    readme_content = f"""# Deployment Backup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Backup Date
{datetime.now().isoformat()}

## Contents

### 1. Lambda Deployment Package
- **File**: `lambda_deployment.zip`
- **Description**: Complete Lambda deployment package with all dependencies
- **Contains**: Python dependencies + application code (Linux x86_64 binaries)

### 2. Terraform State
- **Files**: `terraform.tfstate`, `terraform.tfstate.backup`
- **Description**: Infrastructure state for deployment
- **Use**: Can be used to destroy infrastructure or understand deployed resources

### 3. DynamoDB Tables
- **Files**: `*_backup.json`
- **Tables backed up**:
  - `javumbo-users` - User authentication data
  - `javumbo-sessions` - Active session data
  - `javumbo-user-locks` - Distributed lock information

### 4. User Databases (Optional)
- **Directory**: `user_databases/`
- **Description**: Individual user Anki database files (.anki2)
- **Contains**: User flashcard collections

## Deployment Information

Get deployment details from Terraform state:
```bash
cd ../../terraform
terraform output
```

## To Restore

### Restore Infrastructure and Application

```bash
# 1. Copy Lambda package back
cp lambda_deployment.zip ../../

# 2. Deploy infrastructure
cd ../../
./deploy.sh
```

### Restore DynamoDB Data

```bash
# After infrastructure is deployed, restore user data
python3 ../restore_dynamodb.py deployments/backup_TIMESTAMP/
```

### Restore User Databases

```bash
# Upload user databases back to S3
aws s3 sync user_databases/ s3://javumbo-user-dbs-ACCOUNT_ID/
```

## Notes

- Infrastructure creates fresh resources with new IDs/URLs
- DynamoDB restore script will be provided separately
- User databases can be restored individually or in bulk
- Always test deployment before relying on restored data
"""

    readme_file = backup_dir / 'README.md'
    with open(readme_file, 'w') as f:
        f.write(readme_content)

    print(f"   ✅ README created")

def main():
    print("🧹 Javumbo Deployment Backup Script")
    print("=" * 60)

    # Create backup directory
    backup_dir = create_backup_directory()
    print(f"📁 Backup directory: {backup_dir}")
    print()

    # Perform backups
    results = {
        'lambda': backup_lambda_package(backup_dir),
        'terraform': backup_terraform_state(backup_dir),
        'dynamodb': backup_dynamodb_data(backup_dir),
        's3_databases': backup_s3_user_databases(backup_dir)
    }

    print()
    create_readme(backup_dir)

    print()
    print("=" * 60)
    print("✅ Backup Complete!")
    print()
    print(f"📂 Backup location: {backup_dir}")
    print()
    print("Backed up:")
    if results['lambda']:
        print("  ✅ Lambda deployment package")
    if results['terraform']:
        print("  ✅ Terraform state")
    if results['dynamodb']:
        print("  ✅ DynamoDB tables")
    if results['s3_databases']:
        print("  ✅ User database files")

    print()
    print("Next steps:")
    print("  • Keep this backup in a safe location")
    print("  • Can use Lambda package for future deployments")
    print("  • Use restore script to restore DynamoDB data")

if __name__ == '__main__':
    main()
