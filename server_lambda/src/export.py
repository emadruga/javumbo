"""
Export Module for Javumbo Lambda

Handles exporting user collections to Anki Package (.apkg) format.

.apkg format is a ZIP archive containing:
- collection.anki2: SQLite database with all decks, cards, notes, review history
- media: JSON file mapping media filenames to their hash (empty if no media)

This module creates exports entirely in memory to avoid /tmp cleanup issues.
"""

import os
import time
import zipfile
import json
import io
import logging

logger = logging.getLogger(__name__)


def export_user_collection(username: str, db_path: str) -> tuple[bytes, str]:
    """
    Exports user's Anki collection to .apkg format (ZIP archive).

    Args:
        username: User's username (for filename generation)
        db_path: Absolute path to user's .anki2 database file

    Returns:
        tuple: (apkg_bytes, filename)
            - apkg_bytes (bytes): Binary ZIP data ready to send
            - filename (str): Suggested download filename (e.g., "john_export_20250121_143022.apkg")

    Raises:
        FileNotFoundError: If db_path doesn't exist
        Exception: On ZIP creation or I/O errors

    Example:
        >>> apkg_data, filename = export_user_collection('john', '/tmp/john.anki2')
        >>> # In Flask route:
        >>> return send_file(
        ...     io.BytesIO(apkg_data),
        ...     mimetype='application/zip',
        ...     as_attachment=True,
        ...     download_name=filename
        ... )
    """

    # Validate input
    if not os.path.exists(db_path):
        logger.error(f"Database not found for export: {db_path}")
        raise FileNotFoundError(f"Database file not found: {db_path}")

    if not username or not isinstance(username, str):
        raise ValueError(f"Invalid username: {username}")

    logger.info(f"Starting export for user '{username}' from database: {db_path}")

    try:
        # Generate filename with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{username}_export_{timestamp}.apkg"

        # Create ZIP in memory (avoid /tmp filesystem clutter)
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Add user's database as 'collection.anki2'
            zipf.write(db_path, arcname='collection.anki2')
            logger.debug(f"Added collection.anki2 to archive (source: {db_path})")

            # 2. Add empty media file (required by Anki format spec)
            media_json = json.dumps({})  # Empty dict = no media files
            zipf.writestr('media', media_json)
            logger.debug("Added empty media file to archive")

        # Get binary data from buffer
        apkg_bytes = zip_buffer.getvalue()
        apkg_size_kb = len(apkg_bytes) / 1024

        logger.info(f"✓ Export completed for user '{username}': {filename} ({apkg_size_kb:.1f} KB)")

        return apkg_bytes, filename

    except FileNotFoundError:
        # Re-raise with original message
        raise

    except Exception as e:
        logger.exception(f"Failed to create export for user '{username}': {e}")
        raise Exception(f"Export generation failed: {str(e)}")


def validate_apkg_format(apkg_bytes: bytes) -> bool:
    """
    Validates that binary data is a valid .apkg format.

    Checks:
    - Is valid ZIP archive
    - Contains 'collection.anki2' file
    - Contains 'media' file

    Args:
        apkg_bytes: Binary data to validate

    Returns:
        bool: True if valid .apkg format, False otherwise

    Example:
        >>> apkg_data, _ = export_user_collection('john', '/tmp/john.anki2')
        >>> assert validate_apkg_format(apkg_data) == True
    """
    try:
        with zipfile.ZipFile(io.BytesIO(apkg_bytes), 'r') as zipf:
            namelist = zipf.namelist()

            # Must contain exactly these two files
            required_files = {'collection.anki2', 'media'}

            if set(namelist) != required_files:
                logger.warning(f"Invalid .apkg structure. Expected {required_files}, got {set(namelist)}")
                return False

            # Verify collection.anki2 is a valid SQLite database (basic check)
            collection_data = zipf.read('collection.anki2')
            if not collection_data.startswith(b'SQLite format 3'):
                logger.warning("collection.anki2 is not a valid SQLite database")
                return False

            # Verify media is valid JSON
            media_data = zipf.read('media').decode('utf-8')
            json.loads(media_data)  # Will raise if invalid JSON

            return True

    except zipfile.BadZipFile:
        logger.warning("Invalid ZIP format")
        return False
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in media file")
        return False
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False
