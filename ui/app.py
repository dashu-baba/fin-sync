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

                if saved_files:
                    st.session_state["uploads_meta"] = saved_files
                    st.session_state["password"] = password or ""

                    st.success(f"✅ {len(saved_files)} file(s) uploaded successfully.")
                    with st.expander("Review uploaded files"):
                        for m in saved_files:
                            lock_icon = "🔒" if st.session_state["password"] else ""
                            st.write(f"• **{m['name']}** — {m['size_human']} ({m['ext']}) {lock_icon}")

                    st.info("Next step ➜ Parse with Vertex AI and index into Elastic Cloud.")
                else:
                    st.error("No valid files were uploaded.")

# ---- Sidebar Pipeline View ----
with st.sidebar:
    st.header("📊 FinSync Pipeline")
    st.markdown("""
1. Upload files & password ✅  
2. Parse statements (Vertex AI) ⏳  
3. Clean / normalize ⏳  
4. Embed & index (Elastic Cloud) ⏳  
5. Chat & analytics ⏳  
"""
    )
    st.divider()
    st.caption(f"Environment: `{config.environment}`  \nLog file: `{config.log_file}`")
