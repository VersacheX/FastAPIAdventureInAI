import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS

# Import routers
from api.routers import auth_router, users_router, game_ratings_router, worlds_router, deep_memory_router, tokenized_history_router, history_router, saved_games_router

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(game_ratings_router.router)
app.include_router(worlds_router.router)
app.include_router(deep_memory_router.router)
app.include_router(tokenized_history_router.router)
app.include_router(history_router.router)
app.include_router(saved_games_router.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
