#!/usr/bin/env python
"""Development server with hot reload support for geo service"""

import sys
from pathlib import Path

# Add parent directory to path to import common module
# In Docker: common is at /app/common (same level as dev_server.py)
# Locally: common is at ../common (parent directory)
script_dir = Path(__file__).resolve().parent
if not (script_dir / 'common').exists():
    # Running locally, need to go up to project root
    sys.path.insert(0, str(script_dir.parent))

from common.dev_server import run_dev_server


if __name__ == "__main__":
    run_dev_server("geo")
