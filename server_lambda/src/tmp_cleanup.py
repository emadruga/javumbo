"""
/tmp Cleanup Utility for Lambda

Lambda's /tmp directory is 2GB and persists across warm invocations.
This utility provides functions to manage /tmp storage and prevent exhaustion.

Day 5: Basic cleanup utilities for database files
"""

import os
import glob
import time


def get_tmp_size():
    """
    Get total size of /tmp directory in bytes.

    Returns:
        int: Total size in bytes
    """
    total_size = 0

    for dirpath, dirnames, filenames in os.walk('/tmp'):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(filepath)
            except (OSError, FileNotFoundError):
                pass  # File might have been deleted

    return total_size


def list_tmp_files(pattern='*.anki2'):
    """
    List files in /tmp matching a pattern.

    Args:
        pattern (str): Glob pattern to match (default: *.anki2)

    Returns:
        list: List of tuples (filepath, size_bytes, age_seconds)
    """
    files = []

    for filepath in glob.glob(f'/tmp/{pattern}'):
        try:
            stat = os.stat(filepath)
            size = stat.st_size
            age = time.time() - stat.st_mtime

            files.append({
                'path': filepath,
                'size': size,
                'age': age,
                'modified': stat.st_mtime
            })
        except (OSError, FileNotFoundError):
            pass  # File might have been deleted

    return files


def cleanup_old_files(max_age_seconds=3600, pattern='*.anki2', dry_run=False):
    """
    Delete files older than max_age_seconds.

    Args:
        max_age_seconds (int): Maximum age in seconds (default: 3600 = 1 hour)
        pattern (str): Glob pattern to match (default: *.anki2)
        dry_run (bool): If True, don't actually delete (default: False)

    Returns:
        dict: Statistics about cleanup operation
    """
    files = list_tmp_files(pattern)
    deleted_count = 0
    deleted_size = 0
    kept_count = 0
    kept_size = 0

    for file in files:
        if file['age'] > max_age_seconds:
            # File is too old, delete it
            if not dry_run:
                try:
                    os.remove(file['path'])
                    deleted_count += 1
                    deleted_size += file['size']
                except (OSError, FileNotFoundError):
                    pass  # File might have been deleted by another process
            else:
                deleted_count += 1
                deleted_size += file['size']
        else:
            # File is recent, keep it
            kept_count += 1
            kept_size += file['size']

    return {
        'deleted_count': deleted_count,
        'deleted_size_bytes': deleted_size,
        'deleted_size_mb': deleted_size / (1024 * 1024),
        'kept_count': kept_count,
        'kept_size_bytes': kept_size,
        'kept_size_mb': kept_size / (1024 * 1024),
        'dry_run': dry_run
    }


def cleanup_by_size(target_size_mb=1500, pattern='*.anki2', dry_run=False):
    """
    Delete oldest files until /tmp is below target size.

    Lambda /tmp is 2GB (2048MB). This function ensures we stay below a target.

    Args:
        target_size_mb (int): Target size in MB (default: 1500MB)
        pattern (str): Glob pattern to match (default: *.anki2)
        dry_run (bool): If True, don't actually delete (default: False)

    Returns:
        dict: Statistics about cleanup operation
    """
    target_size_bytes = target_size_mb * 1024 * 1024

    # Get current /tmp size
    current_size = get_tmp_size()

    if current_size <= target_size_bytes:
        return {
            'deleted_count': 0,
            'deleted_size_bytes': 0,
            'deleted_size_mb': 0,
            'initial_size_mb': current_size / (1024 * 1024),
            'final_size_mb': current_size / (1024 * 1024),
            'target_size_mb': target_size_mb,
            'dry_run': dry_run,
            'message': 'No cleanup needed'
        }

    # Get all matching files, sorted by age (oldest first)
    files = list_tmp_files(pattern)
    files.sort(key=lambda f: f['modified'])  # Oldest first

    deleted_count = 0
    deleted_size = 0

    for file in files:
        # Check if we've reached target
        if current_size <= target_size_bytes:
            break

        # Delete file
        if not dry_run:
            try:
                os.remove(file['path'])
                deleted_count += 1
                deleted_size += file['size']
                current_size -= file['size']
            except (OSError, FileNotFoundError):
                pass  # File might have been deleted by another process
        else:
            deleted_count += 1
            deleted_size += file['size']
            current_size -= file['size']

    return {
        'deleted_count': deleted_count,
        'deleted_size_bytes': deleted_size,
        'deleted_size_mb': deleted_size / (1024 * 1024),
        'initial_size_mb': get_tmp_size() / (1024 * 1024),
        'final_size_mb': current_size / (1024 * 1024),
        'target_size_mb': target_size_mb,
        'dry_run': dry_run,
        'message': f'Cleaned up {deleted_count} files to reach target size'
    }


def get_tmp_stats():
    """
    Get statistics about /tmp directory.

    Returns:
        dict: Statistics including size, file count, oldest file
    """
    total_size = get_tmp_size()
    files = list_tmp_files('*')  # All files

    if not files:
        return {
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'file_count': 0,
            'oldest_file': None,
            'oldest_age_seconds': None,
            'newest_file': None,
            'newest_age_seconds': None
        }

    oldest_file = max(files, key=lambda f: f['age'])
    newest_file = min(files, key=lambda f: f['age'])

    return {
        'total_size_bytes': total_size,
        'total_size_mb': total_size / (1024 * 1024),
        'total_capacity_mb': 2048,  # Lambda /tmp is 2GB
        'usage_percent': (total_size / (2048 * 1024 * 1024)) * 100,
        'file_count': len(files),
        'oldest_file': oldest_file['path'],
        'oldest_age_seconds': oldest_file['age'],
        'oldest_age_hours': oldest_file['age'] / 3600,
        'newest_file': newest_file['path'],
        'newest_age_seconds': newest_file['age'],
        'newest_age_hours': newest_file['age'] / 3600
    }


# Lambda handler helper function
def lambda_cleanup_hook(max_age_seconds=3600):
    """
    Cleanup function to call at the end of Lambda handler.

    This is a lightweight cleanup that runs after each Lambda invocation.
    It deletes files older than max_age_seconds (default: 1 hour).

    Usage in Lambda handler:
        def lambda_handler(event, context):
            try:
                # ... your Lambda code ...
                return response
            finally:
                # Cleanup old files
                from tmp_cleanup import lambda_cleanup_hook
                lambda_cleanup_hook()

    Args:
        max_age_seconds (int): Maximum age in seconds (default: 3600 = 1 hour)
    """
    stats = cleanup_old_files(max_age_seconds, pattern='*.anki2', dry_run=False)
    if stats['deleted_count'] > 0:
        print(f"[tmp_cleanup] Deleted {stats['deleted_count']} old files ({stats['deleted_size_mb']:.1f}MB)")
    return stats
