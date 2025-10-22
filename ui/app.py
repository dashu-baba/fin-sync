from __future__ import annotations
import uuid
from pathlib import Path
from typing import List, Dict
import sys
import streamlit as st

# Ensure project root is on sys.path for absolute imports like `core.*`
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import config
from core.logger import get_logger
from core.utils import human_size, safe_write
from ingestion import read_pdf, parse_pdf_to_json
from elastic import embed_texts, embedding_dim, ensure_index, to_doc, index_docs

log = get_logger("ui")

st.set_page_config(
    page_title="FinSync · Upload",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.title("💰 FinSync — Upload Bank Statements")
st.caption("Upload one or more bank statements (PDF/CSV). If your PDFs are password-protected, enter the password below.")

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
if uploads_meta and any(m["ext"] == "pdf" for m in uploads_meta):
    st.divider()
    if st.button("Parse with Vertex AI ✨", key="vertex_parse"):
        if not config.gcp_project_id:
            log.error("GCP_PROJECT_ID is not configured.")
            st.error("GCP_PROJECT_ID is not configured.")
        else:
            with st.spinner("Calling Vertex AI..."):
                log.info(f"Parsing with Vertex AI: project={config.gcp_project_id} location={config.gcp_location} model={config.vertex_model}")
                parsed_results: List[Dict] = []
                for m in uploads_meta:
                    if m["ext"] != "pdf":
                        continue
                    try:
                        parsed = parse_pdf_to_json(
                            m["path"],
                            password=st.session_state.get("password") or None,
                            gcp_project=config.gcp_project_id,
                            gcp_location=config.gcp_location,
                            vertex_model=config.vertex_model,
                        )
                        parsed_results.append({"meta": m, "parsed": parsed})
                        st.success(f"Parsed {m['name']} — {len(parsed.statements)} items")
                    except Exception as e:
                        log.error(f"Vertex parse failed for {m['name']}: {e}")
                        st.error(f"Failed to parse {m['name']} with Vertex: {e}")
                if parsed_results:
                    st.session_state["parsed_results"] = parsed_results
                    st.info("Ready to index into Elastic Cloud.")

# ---- Index into Elastic Cloud ----
parsed_results: List[Dict] = st.session_state.get("parsed_results", [])
if parsed_results:
    st.divider()
    if st.button("Index to Elastic 🚀", key="elastic_index"):
        if not config.ELASTIC_CLOUD_ENDPOINT or not config.elastic_api_key:
            st.error("Elastic Cloud credentials not configured.")
        else:
            try:
                dim = embedding_dim(project_id=config.gcp_project_id, location=config.gcp_location, model_name=config.vertex_model_embed)
                ensure_index(config.elastic_index_name, vector_dim=dim)
                docs: List[Dict] = []
                for item in parsed_results:
                    parsed = item["parsed"].model_dump()
                    raw_text = "\n\n".join(read_pdf(item["meta"]["path"], password=st.session_state.get("password") or None).pages)
                    text_for_embed = " ".join([
                        parsed.get("accountName", ""),
                        parsed.get("bankName", ""),
                        " ".join(s.get("statementDescription", "") for s in parsed.get("statements", [])),
                    ]).strip()
                    vec = embed_texts([text_for_embed], project_id=config.gcp_project_id, location=config.gcp_location, model_name=config.vertex_model_embed)[0]
                    docs.append(to_doc(parsed, raw_text=raw_text, vector=vec))
                n = index_docs(config.elastic_index_name, docs)
                st.success(f"Indexed {n} document(s) into Elastic Cloud")
            except Exception as e:
                log.error(f"Elastic indexing failed: {e}")
                st.error(f"Indexing failed: {e}")

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
