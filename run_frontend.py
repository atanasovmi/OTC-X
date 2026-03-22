"""
OTC-X Frontend Entry Point
Streamlit dashboard for Swiss OTC market analytics

Run with: streamlit run run_frontend.py
"""

import sys
from pathlib import Path

# Ensure we can import from current directory
frontend_dir = Path(__file__).parent
sys.path.insert(0, str(frontend_dir))

# Import the main app (currently app.py in root, will be modularized in Phase 3)
# For Phase 2, we just provide a clean entry point
import streamlit as st

st.set_page_config(
    page_title="OTC-X Market Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Temporarily import from root app.py until Phase 3 modularization
# This will be replaced with modular imports
root_dir = frontend_dir.parent
app_path = root_dir / "app.py"

if not app_path.exists():
    st.error("Application file not found. Please ensure app.py exists in the project root.")
    st.stop()

# For now, we'll inform about the structure
st.info("""
## OTC-X Architecture Refactoring

**Phase 2 Complete:** Repository restructured with:
- ✅ Backend operations in `backend/operations/`
- ✅ Data files in `backend/data/`
- ✅ Logs in `backend/logs/`
- ✅ Professional entry points: `run_backend.py` and `run_frontend.py`

**Phase 3:** Frontend modularization in progress...

For now, please use: `streamlit run app.py` from the project root.
""")
