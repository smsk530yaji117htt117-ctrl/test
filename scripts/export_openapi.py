"""Export the live OpenAPI schema to docs/openapi.json.

RapidAPI lets providers import endpoints from an OpenAPI file. Committing
a snapshot here keeps the marketplace listing in sync with the deployed API.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.main import app

out = ROOT / "docs" / "openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(app.openapi(), indent=2))
print(f"wrote {out} ({out.stat().st_size} bytes)")
