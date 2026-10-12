"""
Streamlit Community Cloud Canonical Entry Point for Sabad.
Alias entry point that imports and executes app.py.
"""

import sys
import importlib
from pathlib import Path

# Ensure project root is at the head of sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import or reload app.py to execute Streamlit commands
if "app" in sys.modules:
    importlib.reload(sys.modules["app"])
else:
    import app
