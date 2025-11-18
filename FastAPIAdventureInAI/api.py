import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS

# Import routers
from routers import auth, users, game_ratings, worlds, deep_memory, tokenized_history, history, saved_games

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
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(game_ratings.router)
app.include_router(worlds.router)
app.include_router(deep_memory.router)
app.include_router(tokenized_history.router)
app.include_router(history.router)
app.include_router(saved_games.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
