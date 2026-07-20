import os
import sys

# Under `python -m src` the repo ROOT (not `src/`) is on sys.path, so the bare
# `api:app` import string can't resolve. Put `src/` on the path first so the
# documented run command works without a PYTHONPATH=src workaround.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8003"))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
