# Streamlit Cloud entry point
# Runs the main dashboard from scripts/run_dashboard.py

import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
os.chdir(project_root)

# Execute the dashboard script
with open(os.path.join(project_root, "scripts", "run_dashboard.py"), "r", encoding="utf-8") as f:
    exec(f.read())
