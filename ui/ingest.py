from __future__ import annotations
import uuid
from pathlib import Path
from typing import List, Dict
import os
import streamlit as st

from core.config import config
from core.logger import get_logger
from core.utils import human_size, safe_write, make_id
from ingestion import read_pdf, parse_pdf_to_json
from ingestion.parser_vertex import parse_csv_to_json
from elastic import embed_texts, start_transform, wait_for_first_checkpoint, ensure_transform_monthly
from elastic.indexer import ensure_statements_index, ensure_transactions_index, bulk_index

log = get_logger("ui/ingest")

def render():
# ---- Initialize per-session folder ----
    if "session_upload_dir" not in st.session_state:
        session_id = uuid.uuid4().hex
        session_dir = config.uploads_dir / f"session-{session_id}"
        session_dir.mkdir(parents=True, exist_ok=True)
        st.session_state["session_upload_dir"] = session_dir
        log.info(f"Session folder created: {session_dir}")

    # ---- Upload Form ----
    with st.form("upload_form", clear_on_submit=False):
        files = st.file_uploader(
            "Choose files",
            type=list(config.allowed_ext),
            accept_multiple_files=True,
            help="You can upload multiple statements (PDF or CSV)."
        )
        password = st.text_input(
            "Password (optional)",
            type="password",
            help="If your PDFs are encrypted, enter the password here."
        )
        submitted = st.form_submit_button("Continue ➜")

    # ---- Submission Logic ----
    if submitted:
        if not files:
            st.warning("Please upload at least one file.")
        else:
            if len(files) > config.max_files:
                st.error(f"Too many files. Max allowed: {config.max_files}.")
                log.warning(f"Upload rejected: {len(files)} files > limit {config.max_files}")
            else:
                total_size = sum(f.size for f in files)
                if total_size > config.max_total_mb * 1024 * 1024:
                    st.error(f"Total upload size exceeds {config.max_total_mb} MB.")
                    log.warning(f"Upload rejected: size {total_size / 1e6:.2f} MB")
                else:
                    saved_files: List[Dict] = []
                    parsed_info: List[Dict] = []
                    for f in files:
                        name = Path(f.name).name
                        ext = Path(name).suffix.lower().lstrip(".")
                        if ext not in config.allowed_ext:
                            st.error(f"❌ Unsupported file type: {name}")
                            log.warning(f"Rejected file (ext): {name}")
                            continue

                        target_path = st.session_state["session_upload_dir"] / name
                        try:
                            safe_write(target_path, f.getvalue())
                        except Exception as e:
                            log.error(f"Failed to save {name}: {e}")
                            st.error(f"Could not save {name}. Please try again.")
                            continue

                        meta = {
                            "name": name,
                            "ext": ext,
                            "size_bytes": f.size,
                            "size_human": human_size(f.size),
                            "path": str(target_path),
                        }
                        saved_files.append(meta)
                        log.info(f"Saved upload: {meta}")

                        if ext == "pdf":
                            try:
                                result = read_pdf(target_path, password=password or None)
                                parsed_info.append({
                                    "name": name,
                                    "num_pages": result.num_pages,
                                    "encrypted": result.encrypted,
                                    "title": result.meta.title,
                                })
                                log.info(f"Parsed PDF: name={name} pages={result.num_pages} encrypted={result.encrypted}")
                            except Exception as e:
                                log.error(f"Failed to parse PDF {name}: {e}")
                                st.warning(f"Could not parse {name}. It will be skipped for now.")

                    if saved_files:
                        st.session_state["uploads_meta"] = saved_files
                        st.session_state["password"] = password or ""

                        st.success(f"✅ {len(saved_files)} file(s) uploaded successfully.")
                        with st.expander("Review uploaded files"):
                            for m in saved_files:
                                lock_icon = "🔒" if st.session_state["password"] else ""
                                st.write(f"• **{m['name']}** — {m['size_human']} ({m['ext']}) {lock_icon}")

                        if parsed_info:
                            st.subheader("📄 PDF Parse Summary")
                            for p in parsed_info:
                                enc = "Yes" if p["encrypted"] else "No"
                                st.write(f"• {p['name']} — pages: {p['num_pages']}, encrypted: {enc}, title: {p['title'] or 'N/A'}")
                    else:
                        st.error("No valid files were uploaded.")

    # ---- Vertex AI Parse (persistent via session_state) ----
    uploads_meta: List[Dict] = st.session_state.get("uploads_meta", [])
    if uploads_meta and any(m["ext"] in ("pdf","csv") for m in uploads_meta):
        st.markdown("---")
        st.subheader("📥 Parse & Index")

        embed_txn_desc = st.checkbox(
            "Embed transaction descriptions (semantic txn search)",
            value=False,
            help="Costs more. Enables vector search at per-transaction level.",
        )
        if st.button("Parse with Vertex AI and Index to Elastic"):
            gcp_project = config.gcp_project_id or os.getenv("GCP_PROJECT_ID")
            gcp_location = config.gcp_location or os.getenv("GCP_LOCATION", "us-central1")
            idx_statements = config.elastic_index_statements
            idx_transactions = config.elastic_index_transactions

            with st.status("Validating configuration...", expanded=True) as status:
                if not gcp_project:
                    status.update(label="Missing GCP project.", state="error")
                    st.error("GCP project is not configured.")
                elif not (os.getenv("ELASTIC_CLOUD_ENDPOINT") and os.getenv("ELASTIC_API_KEY")):
                    status.update(label="Elastic credentials missing.", state="error")
                    st.error("Elastic Cloud credentials are not configured.")
                else:
                    status.update(label="Parsing files...", state="running")
                    stmt_docs: List[Dict] = []
                    txn_docs: List[Dict] = []

                    for meta in uploads_meta:
                        path, ext = meta["path"], meta["ext"]
                        status.write(f"Parsing: {meta['name']}")
                        try:
                            parsed = (
                                parse_pdf_to_json(path, st.session_state.get("password"),
                                                gcp_project=gcp_project, gcp_location=gcp_location, vertex_model=config.vertex_model)
                                if ext == "pdf"
                                else parse_csv_to_json(path)
                            )

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

                            status.update(label="Generating embeddings...", state="running")
                            stmt_vec = embed_texts([summary_text], project_id=gcp_project, location=gcp_location, model_name=config.vertex_model_embed)[0]

                            status.update(label="Ensuring indices...", state="running")
                            ensure_statements_index(idx_statements, vector_dim=len(stmt_vec))
                            ensure_transactions_index(idx_transactions, vector_dim=(len(stmt_vec) if embed_txn_desc else None))

                            statement_id = make_id(str(parsed.accountNo), str(parsed.statementFrom), str(parsed.statementTo))
                            source_file = os.path.basename(meta["name"])

                            stmt_doc = {
                                "id": statement_id,
                                "accountNo": str(parsed.accountNo),
                                "bankName": parsed.bankName,
                                "accountName": parsed.accountName,
                                "statementFrom": str(parsed.statementFrom),
                                "statementTo": str(parsed.statementTo),
                                "summary_text": summary_text,
                                "summary_vector": stmt_vec,
                                "meta": {"sourceFile": source_file},
                            }
                            stmt_docs.append(stmt_doc)

                            tx_docs_batch: List[Dict] = []
                            for i, it in enumerate(parsed.statements):
                                txn_id = make_id(str(parsed.accountNo), str(it.statementDate), str(i), str(it.statementAmount), it.statementDescription or "")
                                vec = None
                                if embed_txn_desc:
                                    vec = embed_texts([it.statementDescription or ""], project_id=gcp_project, location=gcp_location, model_name=config.vertex_model_embed)[0]
                                tx = {
                                    "id": txn_id,
                                    "accountNo": str(parsed.accountNo),
                                    "bankName": parsed.bankName,
                                    "accountName": parsed.accountName,
                                    "type": it.statementType,
                                    "amount": float(it.statementAmount),
                                    # omit balance if None to satisfy scaled_float mapping
                                    **({"balance": float(it.statementBalance)} if it.statementBalance is not None else {}),
                                    "description": it.statementDescription or "",
                                    "category": None,
                                    "currency": None,
                                    "sourceStatementId": statement_id,
                                    "sourceFile": source_file,
                                    "timestamp": str(it.statementDate),
                                    **({"desc_vector": vec} if embed_txn_desc and vec is not None else {}),
                                    "@timestamp": str(it.statementDate),
                                }
                                tx_docs_batch.append(tx)

                            txn_docs.extend(tx_docs_batch)
                            status.write(f"Prepared {len(tx_docs_batch)} transactions for {meta['name']}")

                        except Exception as e:
                            log.error(f"Failed on {meta['name']}: {e!r}")
                            status.write(f"Error on {meta['name']}: {e}")
                            st.error(f"Failed on {meta['name']}: {e}")

                    if stmt_docs or txn_docs:
                        status.update(label="Indexing to Elastic...", state="running")
                        if stmt_docs:
                            bulk_index(idx_statements, stmt_docs, id_field="id")
                        if txn_docs:
                            bulk_index(idx_transactions, txn_docs, id_field="id")
                        status.update(label=f"Complete: Indexed {len(stmt_docs)} statement(s) & {len(txn_docs)} transaction(s).", state="complete")
                        st.success(f"✅ Indexed {len(stmt_docs)} statement(s) & {len(txn_docs)} transaction(s).")

                        src = config.elastic_index_transactions
                        dest = config.elastic_index_aggregates_monthly
                        transform_id = config.elastic_transform_id

                        try:
                            ensure_transform_monthly(transform_id, source_index=f"{src}*", dest_index=dest,
                                            calendar_interval="1M", frequency="1h")
                            start_transform(transform_id)

                            # Optional: wait for initial backfill so charts/answers are instant now
                            wait_now = st.checkbox("Wait for first checkpoint (slow, one-time)", value=False)
                            if wait_now:
                                with st.spinner("Waiting for monthly aggregator to complete initial backfill…"):
                                    wait_for_first_checkpoint(transform_id, timeout_sec=180)
                                st.success("Monthly aggregator initial backfill complete.")
                            else:
                                st.info("Monthly aggregator is running in the background (continuous).")
                        except Exception as e:
                            log.error(f"Transform setup failed: {e!r}")
                            st.error(f"Transform setup failed: {e}")
                    else:
                        status.update(label="No documents to index.", state="warning")
                        st.warning("No documents to index.")

    # ---- Sidebar Pipeline View ----
    with st.sidebar:
        st.header("📊 FinSync Pipeline")
        st.markdown("""
    1. Upload files & password ✅  
    2. Parse statements (Vertex AI) ✅  
    3. Clean / normalize ✅  
    4. Embed & index (Elastic Cloud) ✅  
    5. Chat & analytics ⏳  
    """
        )
        st.divider()
        st.caption(f"Environment: `{config.environment}`  \nLog file: `{config.log_file}`")
