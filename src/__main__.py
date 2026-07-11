import sys
from pathlib import Path

# Ensure the flat `src/` package dir is importable so the run path matches the
# test path (top-level imports: `from api import app`, `from config...`).
_SRC = str(Path(__file__).resolve().parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=False)
