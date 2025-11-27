# FastAPI Adventure in AI

An AI-powered interactive text adventure game with dynamic story generation using local LLM models.

## Features

- 🎮 Interactive text-based adventures with AI-generated narratives
- 🤖 Local LLM integration (MythoMax-L2-13B-GPTQ)
- 📚 Smart memory management with three-tier compression system
- 🌍 Multiple pre-built worlds (Terminator Nexus, Mad Max Wasteland)
- 🎭 Content rating system (Family Friendly, Mature, Unrestricted)
- 👥 User accounts with different tier levels
- 💾 Save/load game functionality
- ⚡ Real-time story generation with token budget management

## Architecture

### Backend
- **FastAPI** - Modern async Python web framework
- **SQLAlchemy** - ORM for database management
- **SQLite** - Embedded database (can be swapped for PostgreSQL/MySQL)
- **PyTorch + Transformers** - AI model loading and inference (local GPTQ models)
- **CUDA** - GPU acceleration for model inference (optional)

### Frontend
- **React** - UI framework
- **Axios** - API communication
- **CSS** - Custom styling

### Directory Structure (actual repository layout)
```text
FastAPIAdventureInAI/ # repo root
├── .env.example
├── README.md
├── requirements.txt
├── SETUP.md
├── SETUP_database.py
├── FastAPIAdventureInAI.sln
├── FastAPIAdventureInAI.pyproj
├── quick_setup.bat
├── quick_setup.sh
├── tools/ # utility scripts
│ ├── run_extractor.py
│ ├── scan_site_dumps.py
│ ├── scan_site_dumps_fixed.py
│ ├── generate_dom_json.py
│ └── analyze_hosts.py
├── ai_main.py # helper entry that runs the AI server (runs `ai_server:app`)
└── FastAPIAdventureInAI/ # backend package
 ├── __init__.py
 ├── aiadventureinpythonconstants.py
 ├── config.py
 ├── data_server.py # FastAPI app wiring (includes routers)
 ├── main.py # helper entry that runs the backend (runs `data_server:app`)
 ├── ai_server.py # standalone AI inference server (optional separate process)
 ├── seed_data.py
 ├── setup_database.py
 ├── api/
 │ ├── __init__.py
 │ ├── ai_client_requests.py
 │ ├── routers/
 │ │ ├── __init__.py
 │ │ ├── auth_router.py
 │ │ ├── users_router.py
 │ │ ├── worlds_router.py
 │ │ ├── game_ratings_router.py
 │ │ ├── history_router.py
 │ │ ├── saved_games_router.py
 │ │ ├── tokenized_history_router.py
 │ │ └── deep_memory_router.py
 │ └── services/
 │ ├── __init__.py
 │ ├── data_api_auth_service.py
 │ ├── users_service.py
 │ ├── worlds_service.py
 │ ├── history_service.py
 │ ├── tokenized_history_service.py
 │ ├── deep_memory_service.py
 │ └── saved_games_service.py
 ├── ai/
 │ ├── __init__.py
 │ ├── schemas_ai_server.py
 │ ├── routers/
 │ │ ├── __init__.py
 │ │ ├── root_router.py
 │ │ ├── tokens_router.py
 │ │ └── lore_router.py
 │ ├── services/
 │ │ ├── __init__.py
 │ │ ├── ai_api_service.py
 │ │ ├── ai_modeler_service.py
 │ │ ├── lookup_ai_service.py
 │ │ ├── http_service.py
 │ │ ├── ddgs_service.py
 │ │ └── extractors/
 │ │ ├── __init__.py
 │ │ ├── common.py
 │ │ └── generic_extractor.py
 │ └── lookup_ai/
 │ ├── __init__.py
 │ ├── fetch_sources.py
 │ ├── section_selector.py
 │ ├── query_terms.py
 │ └── services/
 │ ├── __init__.py
 │ ├── wikipedia_service.py
 │ ├── fandom_service.py
 │ ├── lol_wiki_service.py
 │ ├── leagueoflegends_service.py
 │ ├── product_page_service.py
 │ ├── fanlore_service.py
 │ ├── gluwee_service.py
 │ ├── halloweencostumes_service.py
 │ ├── costumerealm_service.py
 │ └── animecharacters_service.py
 ├── business/
 │ ├── __init__.py
 │ ├── converters/
 │ │ ├── __init__.py
 │ │ └── converters.py
 │ ├── dtos/
 │ │ ├── __init__.py
 │ │ └── dtos.py
 │ ├── models/
 │ │ ├── __init__.py
 │ │ └── models.py
 │ └── schemas/
 │ ├── __init__.py
 │ └── schemas_api.py
 ├── shared/
 │ ├── __init__.py
 │ ├── helpers/
 │ │ ├── __init__.py
 │ │ ├── ai_settings.py
 │ │ └── memory_helper.py
 │ └── services/
 │ ├── __init__.py
 │ ├── auth_service.py
 │ └── orm_service.py
 └── tools/
 └── (project-specific helpers and scripts)

adventure-client/ # React frontend
├── package.json
├── package-lock.json
├── public/
│ ├── index.html
│ ├── manifest.json
│ └── robots.txt
└── src/
 ├── index.js
 ├── index.css
 ├── App.js
 ├── App.css
 ├── Login.js
 ├── NewGame.js
 ├── CreateWorld.js
 ├── Game.js
 ├── LoadGame.js
 ├── ManageWorlds.js
 ├── ManageWorlds.js
 ├── config.js
 └── tests/
 └── (react tests)
```


## Prerequisites

### System Requirements
- **Python**:3.10+ (recommended3.10 for best compatibility)
- **Node.js**:16+ and npm (for frontend)
- **CUDA**: Optional, required for GPU acceleration
- **GPU**: Recommended for local model inference (8GB+ VRAM suggested)
- **RAM**:16GB+ recommended
- **Storage**:20GB+ free space for models

### Software Dependencies
- Git
- Python virtual environment (venv)
- Build tools for native packages (Visual Studio Build Tools on Windows or gcc/g++ on Linux)

## Installation

###1. Clone the Repository
```bash
git clone https://github.com/VersacheX/FastAPIAdventureInAI.git
cd FastAPIAdventureInAI
```

###2. Backend Setup

#### Create Python Virtual Environment
```bash
cd FastAPIAdventureInAI
python -m venv env
```

#### Activate Virtual Environment
**Windows (PowerShell):**
```powershell
.\\env\\Scripts\\Activate.ps1
```

**Windows (CMD):**
```cmd
.\\env\\Scripts\\activate.bat
```

**Linux/Mac:**
```bash
source env/bin/activate
```

#### Install Python Dependencies
```bash
pip install -r requirements.txt
```

If you have CUDA/PyTorch compatibility issues, install PyTorch separately using the instructions from the PyTorch website for your CUDA version.

#### Configure Database
Edit `FastAPIAdventureInAI/config.py` to set your database connection (default is SQLite):
```python
DATABASE_URL = "sqlite:///./adventure.db"
```

#### Create Database Tables
```bash
python -c "from dependencies import engine; from business.models import Base; Base.metadata.create_all(bind=engine)"
```

#### Seed Initial Data
```bash
python seed_data.py
```

This will create default game ratings, pre-built worlds, AI directive settings, account levels, and an admin user.

## Download AI Model

The project uses a local GPTQ-compatible model. The active model constant is defined in `FastAPIAdventureInAI/ai/services/ai_modeler_service.py` as `AI_MODEL`.

Recommended model: `TheBloke/MythoMax-L2-13B-GPTQ` (or another compatible GPTQ model). Update `AI_MODEL` in `ai/services/ai_modeler_service.py` if you place the model locally or want to switch models.

## Running the Application

You typically run two processes (three if you run the frontend locally):

### Terminal1: AI Inference Server (optional separate process)
You can start the AI server either by running `ai_server.py` directly or using `ai_main.py` which launches the same app with Uvicorn.
Run the standalone AI server which loads the local model and serves inference on port9000:
```bash
cd FastAPIAdventureInAI
.\\env\\Scripts\\Activate.ps1 # or activate your venv
python ai_main.py
```
This starts the AI model server on `http://localhost:9000`.

> Note: `ai_server.py` and the model loader in `ai/services/ai_modeler_service.py` are responsible for loading the local GPTQ model. If you prefer the backend to directly load the model into FastAPI app state, the code already supports loading the model into `app.state`.

### Terminal2: FastAPI Backend
Start the backend API (uses `data_server.py` via `main.py`):
```bash
cd FastAPIAdventureInAI
.\\env\\Scripts\\Activate.ps1
python main.py
```
This starts the API server (default host `0.0.0.0`) on port8080 by default.

Alternatively you can run:
```bash
python data_server.py
```

### Terminal3: React Frontend
```bash
cd adventure-client
npm install
npm start
```
This starts the frontend development server on `http://localhost:3000`.

## Usage

1. Open browser to `http://localhost:3000`
2. Login with the seeded admin account (if present) or register a user
3. Create a new game and start playing

## Configuration

### API Settings (`FastAPIAdventureInAI/config.py`)
```python
SECRET_KEY = "your-secret-key-here" # Change in production!
DATABASE_URL = "sqlite:///./adventure.db"
AI_SERVER_URL = "http://127.0.0.1:9000"
CORS_ORIGINS = ["http://localhost:3000"]
```

### AI Model Settings
Token budgets and memory limits can be adjusted in the AI helpers and settings files under `ai/` and `shared/helpers/`.

## Memory Management System

The application uses a three-tier memory compression system:
1. Recent History (uncompressed): last entries kept in full
2. Tokenized Chunks (compressed): older entries summarized into token-sized blocks
3. Deep Memory (ultra-compressed): ancient history compressed further

This keeps prompts within model context windows while preserving key story information.

## Development

### Adding API Endpoints
1. Create/edit a router under `api/routers/` or `ai/routers/` for AI-specific endpoints
2. Register the router in `data_server.py` (or main wiring)

### Database Migrations
When changing models:
1. Update models under `business/models/`
2. Update the database schema manually or integrate Alembic

## Troubleshooting

### Common issues
- Ensure virtual environment is activated and dependencies installed
- For CUDA OOM errors: use a smaller model, reduce memory usage, or run on CPU
- If ports are in use, change the port in `main.py` or `ai_server.py`

## API Documentation
Once running backend, visit:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

## Security Notes
- Change `SECRET_KEY` and default passwords before production
- Use HTTPS and proper credentials in production

## License
Add your license here.
