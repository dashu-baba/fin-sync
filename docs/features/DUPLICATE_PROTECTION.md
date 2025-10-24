# Duplicate Upload Protection

## Overview

The FinSync application now includes comprehensive duplicate upload protection to prevent users from accidentally uploading the same bank statement multiple times. This feature ensures data integrity and prevents duplicate entries in Elasticsearch.

## Protection Layers

### 1. **File-Based Duplicate Detection**

#### 1.1 Filename Check
- **What it does**: Checks if a file with the same name already exists in the upload directory
- **When it runs**: Before file upload
- **User message**: "❌ File '{filename}' already exists. Please rename the file or delete the existing one."

#### 1.2 Content Hash Check
- **What it does**: Calculates SHA-256 hash of file content and compares with existing files
- **When it runs**: Before file upload
- **Why it's important**: Catches cases where users rename a file and try to upload it again
- **User message**: "❌ This file has already been uploaded as '{existing_filename}'. The content is identical even though the filename may be different."

### 2. **Metadata-Based Duplicate Detection**

#### 2.1 Statement Period Check
- **What it does**: Queries Elasticsearch to check if a statement with the same account number and statement period already exists
- **When it runs**: After PDF parsing, before indexing
- **Query criteria**:
  - Account Number (exact match)
  - Statement From Date (exact match)
  - Statement To Date (exact match)
- **User message**: "❌ A statement for account **{account_no}** covering the period **{statement_from}** to **{statement_to}** already exists. Previously uploaded as: `{existing_file}`"

## Implementation Details

### Modified Files

1. **`ui/services/upload_service.py`**
   - Added `check_duplicate_by_hash()` - Checks for duplicate file content
   - Added `check_duplicate_by_name()` - Checks for duplicate filename
   - Added `check_duplicate_in_elasticsearch()` - Checks for duplicate statement in Elasticsearch

2. **`ui/views/ingest_page.py`**
   - Integrated duplicate checks into upload flow
   - Added pre-upload validation (filename + hash)
   - Added post-parse validation (Elasticsearch metadata)

3. **`ui/components/upload_form.py`**
   - Added user-facing information box about duplicate protection
   - Provides transparency about what checks are performed

### Code Structure

```python
# Check 1: Filename duplicate
if UploadService.check_duplicate_by_name(file.name, upload_dir):
    # Block upload

# Check 2: Content hash duplicate
file_content = file.getvalue()
is_duplicate, existing_filename = UploadService.check_duplicate_by_hash(
    file_content, upload_dir
)
if is_duplicate:
    # Block upload

# Check 3: After parsing, check Elasticsearch
# Note: parsed is a Pydantic ParsedStatement object
account_no = str(parsed.accountNo)
statement_from = parsed.statementFrom.isoformat()  # Convert date to ISO string
statement_to = parsed.statementTo.isoformat()      # Convert date to ISO string

is_duplicate, existing_file = UploadService.check_duplicate_in_elasticsearch(
    account_no, statement_from, statement_to
)
if is_duplicate:
    # Block upload
```

### Implementation Notes

**Important**: The `parsed` object returned from `ParseService.parse_file()` is a Pydantic `ParsedStatement` model, not a dictionary. Access attributes directly:

```python
# ✅ Correct
account_no = str(parsed.accountNo)
statement_from = parsed.statementFrom.isoformat()

# ❌ Wrong
account_no = parsed.get("accountNo")  # Will fail - ParsedStatement has no .get()
```

**Date Handling**: The `statementFrom` and `statementTo` fields are Python `date` objects. Convert to ISO format strings for Elasticsearch queries using `.isoformat()`.

**Elasticsearch Client**: Import the `es()` function from `elastic.client`, not `get_client()`:

```python
# ✅ Correct
from elastic.client import es
client = es()

# ❌ Wrong
from elastic.client import get_client  # This function doesn't exist
```

## User Experience

### Upload Form Display

When users access the upload page, they now see:

```
🛡️ Duplicate Protection Enabled

The system automatically checks for:
- Files with the same content (even if renamed)
- Statements for the same account and period

This prevents duplicate data in your financial records.
```

### Error Messages

Users receive clear, actionable error messages when duplicates are detected:

1. **Duplicate Filename**:
   - Error: "File already exists"
   - Action: Rename file or delete existing one

2. **Duplicate Content**:
   - Error: "Same content uploaded previously"
   - Shows: Original filename
   - Action: Use a different file

3. **Duplicate Statement Period**:
   - Error: "Statement period already exists"
   - Shows: Account number, date range, original file
   - Action: Upload a different statement period

## Benefits

1. **Data Integrity**: Prevents duplicate transactions in the database
2. **User Experience**: Clear feedback about why upload was blocked
3. **Cost Optimization**: Avoids unnecessary Vertex AI API calls for duplicate files
4. **Storage Efficiency**: Prevents storing duplicate files

## Technical Considerations

### Performance
- Hash calculation is performed in-memory for uploaded files
- File comparison only scans the upload directory (typically small)
- Elasticsearch query is optimized with exact term matches
- Early exit on first duplicate detection
- Works with both local filesystem and GCS storage backends

### Storage Backend Support

The duplicate detection system works seamlessly with **both local and GCS storage**:

- **Local Development**: Checks files in `data/uploads/` directory
- **Production (GCS)**: Checks files in GCS bucket via storage backend API
- **Auto-Detection**: Automatically uses the correct method based on environment

```python
# Automatic storage backend detection
use_storage_backend = config.environment == "production" and config.gcs_bucket is not None

# Works for both local and GCS
is_duplicate, filename = UploadService.check_duplicate_by_hash(
    file_content, upload_dir, use_storage_backend
)
```

See [`docs/STORAGE_BACKEND_IMPLEMENTATION.md`](STORAGE_BACKEND_IMPLEMENTATION.md) for details.

### Error Handling
- If Elasticsearch check fails, the upload proceeds (fail-open approach)
- Errors are logged for debugging
- Users are not blocked due to infrastructure issues

### Security
- Uses SHA-256 for cryptographically secure hash comparison
- Password-protected PDFs are supported
- File access is limited to upload directory

## Future Enhancements

Potential improvements for future versions:

1. **Partial Overlap Detection**: Warn if statement periods partially overlap
2. **User Override**: Allow admin users to force upload duplicates if needed
3. **Duplicate Management UI**: Interface to view and manage existing uploads
4. **Bulk Upload**: Handle multiple files with batch duplicate checking
5. **Audit Trail**: Track duplicate upload attempts for analysis

## Testing Scenarios

### Test Case 1: Exact Duplicate
1. Upload a bank statement: `statement_jan_2024.pdf`
2. Try to upload the same file again
3. Expected: Blocked by filename check

### Test Case 2: Renamed Duplicate
1. Upload a bank statement: `statement_jan_2024.pdf`
2. Rename to `statement_jan_2024_v2.pdf` and upload
3. Expected: Blocked by hash check

### Test Case 3: Same Statement Period
1. Upload a statement for Account 123456, Jan 1-31, 2024
2. Upload a different file for the same account and period
3. Expected: Blocked by Elasticsearch check

### Test Case 4: Different Statement Period
1. Upload a statement for Account 123456, Jan 1-31, 2024
2. Upload a statement for Account 123456, Feb 1-28, 2024
3. Expected: Both uploads succeed

## Logging

All duplicate detection events are logged with appropriate severity:

```python
# Warning level for blocked duplicates
log.warning(f"Upload blocked: duplicate filename {filename}")
log.warning(f"Upload blocked: duplicate content hash for {filename}")
log.warning(f"Upload blocked: duplicate statement for account {account_no}")

# Error level for check failures
log.error(f"Error checking Elasticsearch for duplicates: {error}")
```

## Configuration

No additional configuration is required. The duplicate protection feature uses existing configuration:

- `config.uploads_dir`: Directory to check for duplicate files
- `config.elastic_index_statements`: Index to query for duplicate statements

## Monitoring

Monitor these metrics to track duplicate upload patterns:

1. **Duplicate Upload Attempts**: Count of blocked uploads
2. **Detection Method**: Which check caught the duplicate (filename/hash/metadata)
3. **User Behavior**: Frequency of duplicate upload attempts per user
4. **False Positives**: Cases where legitimate uploads were blocked

## Automatic Cleanup on Failure

### Overview

To prevent files from being permanently blocked after failed uploads, the system now **automatically deletes files** when processing fails. This ensures users can retry uploads without manual intervention.

### When Cleanup Happens

Files are automatically deleted in the following scenarios:

1. **Parsing Failure**
   - File saved → Parsing fails → **File automatically deleted**
   - Examples: Validation errors, missing required fields, Vertex AI errors
   - User sees: "🗑️ Removed {filename} - you can try uploading again."

2. **Duplicate Statement Detection**
   - File saved → Parsing succeeds → Duplicate found in Elasticsearch → **File automatically deleted**
   - User sees: "❌ Statement already exists..." error message
   - File is cleaned up to allow different statement upload

### Implementation

```python
# In ui/views/ingest_page.py
saved_filename = None  # Track for cleanup
try:
    # Save file
    meta = UploadService.process_upload(file, password=password)
    saved_filename = meta["name"]
    
    # Parse and process
    parsed = ParseService.parse_file(...)
    
except Exception as e:
    # Automatic cleanup on failure
    if saved_filename:
        UploadService.delete_file(saved_filename)
        st.info(f"🗑️ Removed {saved_filename} - you can try uploading again.")
```

### Benefits

- ✅ **No orphaned files** - Failed uploads don't permanently block re-uploads
- ✅ **Seamless retry** - Users can immediately re-upload after fixing issues
- ✅ **No manual intervention** - System automatically handles cleanup
- ✅ **Clear feedback** - Users know when files are removed

## Manual File Deletion

### Delete Button in UI

Users can now manually delete uploaded files through the "Previously Uploaded Files" section:

1. **Location**: Bottom of the Ingest page
2. **Interface**: Each file has a 🗑️ delete button
3. **Confirmation**: Click → Spinner → Success/Error message
4. **Auto-refresh**: List refreshes after successful deletion

### User Interface

```
📁 Previously Uploaded Files
────────────────────────────────────────────────────
Total Files: 3    Total Storage: 2.4 MB    Storage Type: Local

1. 📄 statement_jan.pdf       1.2 MB    [🗑️]
2. 📄 statement_feb.pdf       1.0 MB    [🗑️]
3. 📄 statement_mar.pdf       0.2 MB    [🗑️]
```

### Use Cases

- **Failed Processing**: Remove files that failed to parse/index
- **Wrong File**: Delete incorrectly uploaded files
- **Re-upload**: Clear old version before uploading new one
- **Storage Management**: Free up storage space

### Implementation

```python
# In ui/components/uploaded_files_display.py
if st.button("🗑️", key=f"delete_{file_info['name']}"):
    with st.spinner(f"Deleting {file_info['name']}..."):
        if UploadService.delete_file(file_info['name']):
            st.success(f"✅ Deleted {file_info['name']}")
            st.rerun()
        else:
            st.error(f"❌ Failed to delete {file_info['name']}")
```

## Support

If users encounter issues with duplicate detection:

1. **Legitimate Re-upload**: 
   - **Automatic**: If upload failed, file is auto-deleted; just retry
   - **Manual**: Use the 🗑️ button in "Previously Uploaded Files" to delete
   - **Alternative**: Delete the statement data from Elasticsearch if already indexed
   
2. **False Positive**: If the system incorrectly flags a duplicate:
   - Check logs for the specific check that failed
   - Verify account numbers and dates in both statements
   - Use manual delete button to remove the blocking file
   - Contact support with log details

3. **Stuck Files**: If a file won't delete:
   - Check logs for error details
   - Verify storage backend permissions (local or GCS)
   - For local: Check file permissions in `data/uploads/`
   - For GCS: Verify service account has delete permissions

## Conclusion

The duplicate upload protection feature provides a robust, multi-layered defense against accidental duplicate uploads while maintaining a smooth user experience. With automatic cleanup on failure and manual delete options, the system balances security, performance, and usability to ensure data integrity in the FinSync system.

