import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import configuration from environment
from config import CORS_ORIGINS

from ai.routers.root_router import router as root_router
from ai.routers.tokens_router import router as tokens_router
from ai.routers.lore_router import router as lore_router
from ai.services.ai_modeler_service import load_story_generater_to_app_state

app = FastAPI()

load_story_generater_to_app_state(app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(root_router)
app.include_router(tokens_router)   
app.include_router(lore_router)

if __name__ == "__main__":    
    uvicorn.run(app, host="0.0.0.0", port=9000)