#!/usr/bin/env python3
"""
Restore DynamoDB data from backup files.
Usage: python3 restore_dynamodb.py deployments/backup_TIMESTAMP/
"""

import boto3
import json
import sys
from pathlib import Path

def restore_table(backup_file):
    """Restore a single DynamoDB table from backup."""
    dynamodb = boto3.client('dynamodb', region_name='us-east-1')

    print(f"📥 Restoring from: {backup_file.name}")

    # Load backup data
    with open(backup_file, 'r') as f:
        backup_data = json.load(f)

    table_name = backup_data['table_name']
    items = backup_data['items']

    print(f"   Table: {table_name}")
    print(f"   Items to restore: {len(items)}")

    if len(items) == 0:
        print(f"   ⚠️  No items to restore")
        return True

    # Restore items in batches of 25 (DynamoDB limit)
    batch_size = 25
    restored_count = 0

    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]

        # Build batch write request
        request_items = {
            table_name: [
                {'PutRequest': {'Item': item}}
                for item in batch
            ]
        }

        try:
            response = dynamodb.batch_write_item(RequestItems=request_items)

            # Handle unprocessed items
            while response.get('UnprocessedItems'):
                print(f"   ⏳ Retrying unprocessed items...")
                response = dynamodb.batch_write_item(
                    RequestItems=response['UnprocessedItems']
                )

            restored_count += len(batch)
            print(f"   📝 Restored {restored_count}/{len(items)} items", end='\r')

        except Exception as e:
            print(f"\n   ❌ Error restoring batch: {e}")
            return False

    print(f"\n   ✅ Restored {restored_count} items to {table_name}")
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 restore_dynamodb.py <backup_directory>")
        print("Example: python3 restore_dynamodb.py deployments/backup_20251217_194204/")
        sys.exit(1)

    backup_dir = Path(sys.argv[1])

    if not backup_dir.exists():
        print(f"❌ Backup directory not found: {backup_dir}")
        sys.exit(1)

    print("🔄 Javumbo DynamoDB Restore Script")
    print("=" * 60)
    print(f"📂 Backup directory: {backup_dir}")
    print()

    # Find all backup files
    backup_files = list(backup_dir.glob('*_backup.json'))

    if not backup_files:
        print("❌ No backup files found in directory")
        sys.exit(1)

    print(f"Found {len(backup_files)} backup file(s):")
    for f in backup_files:
        print(f"  • {f.name}")
    print()

    # Confirm restore
    response = input("⚠️  This will overwrite existing data. Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Restore cancelled")
        sys.exit(0)

    print()

    # Restore each table
    success_count = 0
    for backup_file in backup_files:
        if restore_table(backup_file):
            success_count += 1
        print()

    print("=" * 60)
    if success_count == len(backup_files):
        print("✅ All tables restored successfully!")
    else:
        print(f"⚠️  Restored {success_count}/{len(backup_files)} tables")

    print()
    print("Next steps:")
    print("  • Test application to verify data was restored correctly")
    print("  • Check user login with restored credentials")

if __name__ == '__main__':
    main()
