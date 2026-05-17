"""Test bootstrap for scripts moved out of ml-service.

Python imports this module automatically from the script directory. Keep test
scripts runnable with commands such as:

    python testing/ml-service/test_simplification_consistency.py
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ML_SERVICE_ROOT = REPO_ROOT / "ml-service"

if str(ML_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_SERVICE_ROOT))

os.environ.setdefault("THINC_NO_TORCH", "1")

try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=ML_SERVICE_ROOT / ".env")
except Exception:
    pass
