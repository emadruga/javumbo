#!/usr/bin/env python3
"""
Clean up S3 buckets including all versions and delete markers.
This script is useful for cleaning up before terraform destroy.
"""

import boto3
import sys

def delete_all_object_versions(bucket_name):
    """Delete all versions and delete markers from an S3 bucket."""
    s3 = boto3.client('s3')

    print(f"🗑️  Deleting all objects from bucket: {bucket_name}")

    try:
        # Get bucket versioning status
        versioning = s3.get_bucket_versioning(Bucket=bucket_name)
        is_versioned = versioning.get('Status') == 'Enabled'

        if is_versioned:
            print(f"   Bucket is versioned - will delete all versions")

        # Paginate through all object versions
        paginator = s3.get_paginator('list_object_versions')
        delete_markers = []
        versions = []

        for page in paginator.paginate(Bucket=bucket_name):
            # Collect delete markers
            if 'DeleteMarkers' in page:
                for marker in page['DeleteMarkers']:
                    delete_markers.append({
                        'Key': marker['Key'],
                        'VersionId': marker['VersionId']
                    })

            # Collect versions
            if 'Versions' in page:
                for version in page['Versions']:
                    versions.append({
                        'Key': version['Key'],
                        'VersionId': version['VersionId']
                    })

        # Delete all versions
        total_deleted = 0
        if versions:
            print(f"   Deleting {len(versions)} object versions...")
            # Delete in batches of 1000 (AWS limit)
            for i in range(0, len(versions), 1000):
                batch = versions[i:i+1000]
                s3.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': batch}
                )
                total_deleted += len(batch)

        # Delete all delete markers
        if delete_markers:
            print(f"   Deleting {len(delete_markers)} delete markers...")
            for i in range(0, len(delete_markers), 1000):
                batch = delete_markers[i:i+1000]
                s3.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': batch}
                )
                total_deleted += len(batch)

        if total_deleted == 0:
            print(f"   Bucket is already empty")
        else:
            print(f"   ✅ Deleted {total_deleted} objects/versions")

        return True

    except s3.exceptions.NoSuchBucket:
        print(f"   ⚠️  Bucket does not exist (already deleted)")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    # Get bucket names from terraform output or use defaults
    buckets = [
        'javumbo-user-dbs-540966371089',
        'javumbo-frontend-prod-540966371089'
    ]

    print("🧹 Javumbo S3 Cleanup Script")
    print("=" * 50)

    for bucket in buckets:
        delete_all_object_versions(bucket)
        print()

    print("✅ Cleanup complete!")
    print("\nNow you can run: terraform destroy -auto-approve")

if __name__ == '__main__':
    main()
