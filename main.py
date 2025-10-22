from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path
from loguru import logger

# --- Ensure project root is in path ---
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# --- Import core setup ---
from core.config import config
from core.logger import get_logger

log = get_logger("main")

def verify_environment() -> None:
    """Check environment prerequisites before launching Streamlit."""
    log.info(f"Starting FinSync in '{config.environment}' mode")

    # Basic sanity checks
    required_dirs = [config.data_dir, config.uploads_dir, config.logs_dir]
    for d in required_dirs:
        if not d.exists():
            log.warning(f"Creating missing directory: {d}")
            d.mkdir(parents=True, exist_ok=True)

    # Check that Google credentials and Elastic Cloud ID exist
    if not os.getenv("ELASTIC_CLOUD_ID"):
        log.warning("⚠️  ELASTIC_CLOUD_ID not set — Elastic Cloud features may not work")
    if not os.getenv("GCP_PROJECT_ID"):
        log.warning("⚠️  GCP_PROJECT_ID not set — Vertex AI features may not work")

def launch_streamlit() -> None:
    """Launch the Streamlit UI programmatically."""
    ui_path = ROOT_DIR / "ui" / "app.py"
    if not ui_path.exists():
        log.error(f"UI app not found at {ui_path}")
        sys.exit(1)

    log.info(f"Launching Streamlit app: {ui_path}")
    port = os.getenv("PORT", config.app_port)

    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(ui_path), "--server.port", str(port), "--server.headless", "true"],
            check=True,
            cwd=str(ROOT_DIR),
        )
    except KeyboardInterrupt:
        log.info("FinSync stopped by user.")
    except subprocess.CalledProcessError as e:
        log.error(f"Streamlit failed to start: {e}")
        sys.exit(1)

def main() -> None:
    verify_environment()
    launch_streamlit()

if __name__ == "__main__":
    main()
