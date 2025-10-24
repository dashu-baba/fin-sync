"""Ingest page - orchestrates file upload, parsing, and indexing."""
from __future__ import annotations
from typing import List, Dict
import streamlit as st

from core.logger import get_logger
from core.config import config
from ui.services import SessionManager, UploadService
from ui.components import render_upload_form

log = get_logger("ui/pages/ingest_page")


def render() -> None:
    """Render the ingest page."""
    # Initialize session state
    SessionManager.init_session()
    
    # Main title
    st.title("💰 FinSync — Personal Finance Manager")
    st.header("📥 Ingest Bank Statements")
    st.caption("Upload your bank statement PDF - it will be automatically parsed and indexed")
    
    # Render upload form
    files, password, submitted = render_upload_form()
    
    # Handle form submission - auto parse and index
    if submitted and files:
        _handle_upload_and_index(files, password)


def _handle_upload_and_index(files, password: str) -> None:
    """
    Handle file upload, parse, and index in one flow.
    
    Args:
        files: Uploaded files from Streamlit
        password: Password for encrypted PDFs
    """
    import os
    from ui.services import ParseService
    from elastic.indexer import ensure_statements_index, ensure_transactions_index, ensure_transaction_alias
    
    # Validate files
    is_valid, error_msg = UploadService.validate_files(files)
    if not is_valid:
        if error_msg:
            st.warning(error_msg) if "at least one" in error_msg else st.error(error_msg)
            if "at least one" not in error_msg:
                log.warning(f"Upload validation failed: {error_msg}")
        return
    
    # Process upload
    upload_dir = SessionManager.get_upload_dir()
    
    # Check for duplicate files before uploading
    for file in files:
        # Check by filename
        if UploadService.check_duplicate_by_name(file.name, upload_dir):
            st.error(f"❌ File '{file.name}' already exists. Please rename the file or delete the existing one.")
            log.warning(f"Upload blocked: duplicate filename {file.name}")
            return
        
        # Check by content hash
        file_content = file.getvalue()
        is_duplicate, existing_filename = UploadService.check_duplicate_by_hash(file_content, upload_dir)
        if is_duplicate:
            st.error(
                f"❌ This file has already been uploaded as '{existing_filename}'. "
                f"The content is identical even though the filename may be different."
            )
            log.warning(f"Upload blocked: duplicate content hash for {file.name}")
            return
    gcp_project = config.gcp_project_id or os.getenv("GCP_PROJECT_ID")
    gcp_location = config.gcp_location or os.getenv("GCP_LOCATION", "us-central1")
    idx_statements = config.elastic_index_statements
    idx_transactions = config.elastic_index_transactions
    
    with st.status("Processing your bank statement...", expanded=True) as status:
        # Validate configuration
        is_valid, error_msg = ParseService.validate_config()
        if not is_valid:
            status.update(label=error_msg, state="error")
            st.error(error_msg)
            return
        
        stmt_docs: List[Dict] = []
        txn_docs: List[Dict] = []
        
        for file in files:
            try:
                # Step 1: Save file
                status.update(label=f"Saving {file.name}...", state="running")
                meta = UploadService.process_upload(file, upload_dir, password)
                if not meta:
                    st.error(f"❌ Could not save: {file.name}")
                    continue
                
                # Step 2: Parse with Vertex AI
                status.update(label=f"Parsing {file.name} with Vertex AI...", state="running")
                parsed = ParseService.parse_file(
                    meta["path"],
                    meta["ext"],
                    password=password or None,
                    gcp_project=gcp_project,
                    gcp_location=gcp_location
                )
                
                # Step 2.5: Check for duplicate statement in Elasticsearch
                status.update(label="Checking for duplicate statements...", state="running")
                account_no = str(parsed.accountNo)
                statement_from = parsed.statementFrom.isoformat()  # Convert date to string
                statement_to = parsed.statementTo.isoformat()  # Convert date to string
                
                is_duplicate, existing_file = UploadService.check_duplicate_in_elasticsearch(
                    account_no, statement_from, statement_to
                )
                
                if is_duplicate:
                    status.update(
                        label=f"Duplicate statement detected for account {account_no}",
                        state="error"
                    )
                    st.error(
                        f"❌ A statement for account **{account_no}** covering the period "
                        f"**{statement_from}** to **{statement_to}** already exists.\n\n"
                        f"Previously uploaded as: `{existing_file}`\n\n"
                        f"Please upload a different statement period to avoid duplicate data."
                    )
                    log.warning(
                        f"Upload blocked: duplicate statement for account {account_no}, "
                        f"period {statement_from} to {statement_to}"
                    )
                    return
                
                # Step 3: Ensure indices exist
                status.update(label="Preparing Elasticsearch indices...", state="running")
                ensure_statements_index(idx_statements, vector_dim=config.elastic_vector_dim)
                ensure_transactions_index(idx_transactions)
                ensure_transaction_alias(config.elastic_alias_txn_view, idx_transactions)
                
                # Step 4: Create documents with embeddings (always enabled)
                status.update(label="Generating embeddings...", state="running")
                source_file = os.path.basename(meta["name"])
                
                stmt_docs = ParseService.create_statement_docs(
                    parsed,
                    source_file,
                    gcp_project=gcp_project,
                    gcp_location=gcp_location
                )
                
                for stmt_doc in stmt_docs:
                    tx_docs_batch = ParseService.create_transaction_docs(
                        parsed,
                        stmt_doc["id"],
                        source_file,
                        embed_descriptions=True,  # Always embed
                        gcp_project=gcp_project,
                        gcp_location=gcp_location
                    )
                    txn_docs.extend(tx_docs_batch)
                
                status.write(f"✓ Prepared {len(stmt_docs)} statement(s) and {len(txn_docs)} transaction(s)")
                
            except Exception as e:
                log.error(f"Failed to process {file.name}: {e!r}")
                status.update(label=f"Error processing {file.name}", state="error")
                st.error(f"❌ Failed to process {file.name}: {str(e)}")
                return
        
        # Step 5: Index to Elasticsearch
        if stmt_docs or txn_docs:
            status.update(label="Indexing to Elasticsearch...", state="running")
            ParseService.index_documents(stmt_docs, txn_docs)
            
            status.update(
                label=f"✅ Complete! Indexed {len(stmt_docs)} statement(s) & {len(txn_docs)} transaction(s).",
                state="complete"
            )
            st.success(f"✅ Successfully processed and indexed your bank statement!")
            st.info(f"📊 {len(stmt_docs)} statement(s) • {len(txn_docs)} transaction(s) indexed")
            
            # Save to session
            SessionManager.set_uploads_meta([meta])
            SessionManager.set_password(password or "")
        else:
            status.update(label="No documents to index.", state="complete")
            st.warning("No documents found to index.")

