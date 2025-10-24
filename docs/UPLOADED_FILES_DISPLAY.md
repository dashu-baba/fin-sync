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
- Provides detailed view in expandable section
- Includes refresh button for real-time updates

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
Shows a clean, organized list:
```
📁 Previously Uploaded Files                              🔄 Refresh

┌─────────────────────────────────────────────────────────┐
│ Total Files          Total Storage       Storage Type   │
│      5                   2.4 MB              GCS        │
└─────────────────────────────────────────────────────────┘

These files have been successfully uploaded and indexed.

1. 📄 statement_jan_2024.pdf                     486.5 KB
2. 📄 statement_feb_2024.pdf                     512.3 KB
3. 📄 statement_mar_2024.pdf                     498.7 KB
4. 📄 statement_apr_2024.pdf                     521.1 KB
5. 📄 statement_may_2024.pdf                     456.9 KB

► 📊 View detailed file information
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

## Future Enhancements

Potential improvements:
- Delete file functionality
- File download button
- Search/filter uploaded files
- Sort by date, name, or size
- Preview file contents
- Show upload date/time
- Show indexed vs non-indexed files
- Bulk operations (delete multiple files)

