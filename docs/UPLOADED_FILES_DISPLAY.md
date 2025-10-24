# Uploaded Files Display Feature

## Overview
The uploaded files display feature shows all previously uploaded bank statement PDFs on the Ingest page, allowing users to track what files have been uploaded to the system.

## Components

### `ui/components/uploaded_files_display.py`
New component that displays uploaded files with the following features:

- **File Listing**: Shows all PDF files stored in the configured storage backend
- **Summary Metrics**: Displays:
  - Total number of files
  - Total storage used
  - Storage type (Local or GCS)
- **Refresh Button**: Allows users to manually refresh the file list
- **Detailed View**: Expandable section showing full file paths and metadata

### Functions

#### `get_uploaded_files_list() -> List[Dict]`
Retrieves list of uploaded PDF files from the storage backend.

**Returns:**
```python
[
    {
        "name": "statement.pdf",
        "path": "statement.pdf",  # or gs://bucket/statement.pdf for GCS
        "size_bytes": 123456,
        "size_human": "120.6 KB"
    }
]
```

#### `render_uploaded_files_display() -> None`
Main rendering function that displays the uploaded files UI.

**Features:**
- Automatically detects storage backend (Local or GCS)
- Shows summary metrics at the top
- Lists files with filename and size
- **Delete button (🗑️)** for each file - NEW!
- Provides detailed view in expandable section
- Includes refresh button for real-time updates
- Auto-refreshes after successful deletion

## Integration

### Ingest Page
The component is integrated into the ingest page (`ui/views/ingest_page.py`):

```python
from ui.components import render_uploaded_files_display

def render() -> None:
    # ... upload form ...
    
    # Display previously uploaded files
    render_uploaded_files_display()
```

## Storage Backend Support
Works seamlessly with both storage backends:
- **Local Storage**: Reads from `data/uploads/` directory
- **GCS Storage**: Reads from configured GCS bucket

The component uses the `get_storage_backend()` factory function, which automatically selects the appropriate backend based on the environment configuration.

## User Experience

### Empty State
When no files are uploaded:
```
📭 No files have been uploaded yet. Upload your first bank statement above!
```

### With Files
Shows a clean, organized list with delete functionality:
```
📁 Previously Uploaded Files                              🔄 Refresh

┌─────────────────────────────────────────────────────────┐
│ Total Files          Total Storage       Storage Type   │
│      5                   2.4 MB              GCS        │
└─────────────────────────────────────────────────────────┘

These files have been successfully uploaded and indexed. Use the 🗑️ button to delete files that failed to process.

1. 📄 statement_jan_2024.pdf           486.5 KB    [🗑️]
2. 📄 statement_feb_2024.pdf           512.3 KB    [🗑️]
3. 📄 statement_mar_2024.pdf           498.7 KB    [🗑️]
4. 📄 statement_apr_2024.pdf           521.1 KB    [🗑️]
5. 📄 statement_may_2024.pdf           456.9 KB    [🗑️]

► 📊 View detailed file information
```

### Delete Functionality

Each file now has a delete button (🗑️) that allows users to:
- **Remove failed uploads**: Files that couldn't be parsed or indexed
- **Clear old files**: Remove files no longer needed
- **Retry uploads**: Delete and re-upload corrected files
- **Manage storage**: Free up storage space

**Delete Flow:**
1. User clicks 🗑️ button
2. System shows spinner: "Deleting filename.pdf..."
3. File is removed from storage (local or GCS)
4. Success message: "✅ Deleted filename.pdf"
5. Page auto-refreshes to show updated file list

**Integration with Upload Service:**
```python
# ui/components/uploaded_files_display.py
from ui.services import UploadService

if st.button("🗑️", key=f"delete_{file_info['name']}"):
    with st.spinner(f"Deleting {file_info['name']}..."):
        if UploadService.delete_file(file_info['name']):
            st.success(f"✅ Deleted {file_info['name']}")
            st.rerun()
        else:
            st.error(f"❌ Failed to delete {file_info['name']}")
```

## Testing

Run the test script to verify functionality:

```bash
python3 scripts/test_uploaded_files_display.py
```

This will:
1. Initialize the storage backend
2. List all uploaded files
3. Filter for PDF files
4. Display file information

## Error Handling

The component includes robust error handling:
- Gracefully handles storage backend failures
- Logs errors without breaking the UI
- Shows empty state if file retrieval fails
- Handles individual file read failures

## Implemented Features

- ✅ **Delete file functionality** - Each file has a delete button
- ✅ **Storage backend support** - Works with local and GCS
- ✅ **Auto-refresh** - Page refreshes after deletion
- ✅ **Error handling** - Graceful failure messages
- ✅ **Summary metrics** - Shows total files and storage
- ✅ **Detailed view** - Expandable section with full details

## Future Enhancements

Potential improvements for future versions:
- File download button
- Search/filter uploaded files
- Sort by date, name, or size
- Preview file contents
- Show upload date/time
- Show indexed vs non-indexed files
- Bulk operations (delete multiple files)
- Confirmation dialog before deletion

