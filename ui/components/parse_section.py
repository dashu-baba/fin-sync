"""Parse and index section component."""
from __future__ import annotations
import os
from typing import List, Dict
import streamlit as st

from core.config import config
from core.logger import get_logger
from elastic import embed_texts
from elastic.indexer import ensure_statements_index, ensure_transactions_index
from ui.services import ParseService

log = get_logger("ui/components/parse_section")


def render_parse_section(uploads_meta: List[Dict], password: str) -> None:
    """
    Render the parse and index section.
    
    Args:
        uploads_meta: List of uploaded file metadata
        password: Session password for encrypted PDFs
    """
    if not uploads_meta or not any(m["ext"] in ("pdf", "csv") for m in uploads_meta):
        return
    
    st.markdown("---")
    st.subheader("📥 Parse & Index")
    
    embed_txn_desc = st.checkbox(
        "Embed transaction descriptions (semantic txn search)",
        value=False,
        help="Costs more. Enables vector search at per-transaction level.",
    )
    
    if st.button("Parse with Vertex AI and Index to Elastic"):
        _handle_parse_and_index(uploads_meta, password, embed_txn_desc)


def _handle_parse_and_index(
    uploads_meta: List[Dict],
    password: str,
    embed_txn_desc: bool
) -> None:
    """Handle the parse and index workflow."""
    gcp_project = config.gcp_project_id or os.getenv("GCP_PROJECT_ID")
    gcp_location = config.gcp_location or os.getenv("GCP_LOCATION", "us-central1")
    idx_statements = config.elastic_index_statements
    idx_transactions = config.elastic_index_transactions
    
    with st.status("Validating configuration...", expanded=True) as status:
        # Validate configuration
        is_valid, error_msg = ParseService.validate_config()
        if not is_valid:
            status.update(label=error_msg, state="error")
            st.error(error_msg)
            return
        
        # Parse and prepare documents
        status.update(label="Parsing files...", state="running")
        stmt_docs: List[Dict] = []
        txn_docs: List[Dict] = []
        
        for meta in uploads_meta:
            path, ext = meta["path"], meta["ext"]
            status.write(f"Parsing: {meta['name']}")
            
            try:
                # Parse file
                parsed = ParseService.parse_file(
                    path,
                    ext,
                    password=password or None,
                    gcp_project=gcp_project,
                    gcp_location=gcp_location
                )
                
                # Generate summary embedding
                status.update(label="Generating embeddings...", state="running")
                head_txn = "\n".join(
                    f"{it.statementDate} {it.statementType} {it.statementAmount} {it.statementDescription}"
                    for it in parsed.statements[:200]
                )
                summary_text = (
                    f"Account: {parsed.accountName}\n"
                    f"Bank: {parsed.bankName}\n"
                    f"Range: {parsed.statementFrom}..{parsed.statementTo}\n"
                    f"Transactions:\n{head_txn}"
                )
                stmt_vec = embed_texts(
                    [summary_text],
                    project_id=gcp_project,
                    location=gcp_location,
                    model_name=config.vertex_model_embed
                )[0]
                
                # Ensure indices
                status.update(label="Ensuring indices...", state="running")
                ensure_statements_index(idx_statements, vector_dim=len(stmt_vec))
                ensure_transactions_index(
                    idx_transactions,
                    vector_dim=(len(stmt_vec) if embed_txn_desc else None)
                )
                
                # Create documents
                source_file = os.path.basename(meta["name"])
                stmt_doc = ParseService.create_statement_doc(
                    parsed,
                    source_file,
                    stmt_vec
                )
                stmt_docs.append(stmt_doc)
                
                tx_docs_batch = ParseService.create_transaction_docs(
                    parsed,
                    stmt_doc["id"],
                    source_file,
                    embed_descriptions=embed_txn_desc,
                    gcp_project=gcp_project,
                    gcp_location=gcp_location
                )
                txn_docs.extend(tx_docs_batch)
                status.write(f"Prepared {len(tx_docs_batch)} transactions for {meta['name']}")
                
            except Exception as e:
                log.error(f"Failed on {meta['name']}: {e!r}")
                status.write(f"Error on {meta['name']}: {e}")
                st.error(f"Failed on {meta['name']}: {e}")
        
        # Index documents
        if stmt_docs or txn_docs:
            status.update(label="Indexing to Elastic...", state="running")
            ParseService.index_documents(stmt_docs, txn_docs)
            status.update(
                label=f"Complete: Indexed {len(stmt_docs)} statement(s) & {len(txn_docs)} transaction(s).",
                state="complete"
            )
            st.success(f"✅ Indexed {len(stmt_docs)} statement(s) & {len(txn_docs)} transaction(s).")
            
            # Setup aggregation transform
            _setup_transform(status)
        else:
            status.update(label="No documents to index.", state="warning")
            st.warning("No documents to index.")


def _setup_transform(status) -> None:
    """Setup and start the aggregation transform."""
    try:
        wait_now = st.checkbox(
            "Wait for first checkpoint (slow, one-time)",
            value=False
        )
        ParseService.setup_aggregation_transform(wait_for_checkpoint=wait_now)
        
        if wait_now:
            with st.spinner("Waiting for monthly aggregator to complete initial backfill…"):
                st.success("Monthly aggregator initial backfill complete.")
        else:
            st.info("Monthly aggregator is running in the background (continuous).")
    except Exception as e:
        log.error(f"Transform setup failed: {e!r}")
        st.error(f"Transform setup failed: {e}")

