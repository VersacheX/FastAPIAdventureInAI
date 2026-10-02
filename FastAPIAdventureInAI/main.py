import uvicorn
import os
import logging

logging.basicConfig(level=logging.INFO)

HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "8080"))
RELOAD = os.getenv("API_RELOAD", "true").lower() == "true"

if __name__ == "__main__":
    uvicorn.run(
        "data_server:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
        # Exclude the WSL virtualenv: its Linux symlinks (e.g. lib64) can't be
        # traversed by the Windows file watcher and crash the reloader.
        reload_excludes=[".venv-wsl/*", "env/*", ".venv/*"],
    )
