import uvicorn
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import configuration from environment
from config import CORS_ORIGINS

from ai.routers.authoring_router import router as authoring_router
from ai.services.authoring_modeler_service import load_authoring_model_to_app_state

app = FastAPI()

load_authoring_model_to_app_state(app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(authoring_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9100)
