import uvicorn
import os
import logging

logging.basicConfig(level=logging.INFO)

HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "9000"))
RELOAD = os.getenv("API_RELOAD", "true").lower() == "true"

if __name__ == "__main__":
    uvicorn.run("ai_server:app", host=HOST, port=PORT, reload=False)