import uvicorn
import os
import logging
import sys

logging.basicConfig(level=logging.INFO)

HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "9000"))
RELOAD = os.getenv("API_RELOAD", "true").lower() == "true"

if __name__ == "__main__":
    try:
        uvicorn.run("ai_server:app", host=HOST, port=PORT, reload=False)
    except Exception as e:
        # Log full traceback and print a concise error to stderr so it's visible when the process exits
        logging.exception("Application crashed with an unhandled exception")
        print(f"Application crashed: {e}", file=sys.stderr)
        # Exit with non-zero status to signal failure
        sys.exit(1)