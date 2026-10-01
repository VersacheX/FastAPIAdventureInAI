# FastAPI Adventure in AI

An AI-powered interactive text adventure game with dynamic story generation using local LLM models.

## Features

- 🎮 Interactive text-based adventures with AI-generated narratives
- 🤖 Local LLM integration via **llama.cpp / GGUF** (default: `Qwen2.5-14B Uncensored Instruct`, Q5_K_M)
- 🧩 **Split-server architecture**: a Windows data/API server + a GPU AI inference server (ideal for WSL)
- 📚 Smart memory management with three-tier compression system
- 🌍 Multiple pre-built worlds (Terminator Nexus, Mad Max Wasteland)
- 🎭 Content rating system (Family Friendly, Mature, Unrestricted)
- 👥 User accounts with different tier levels
- 💾 Save/load game functionality
- ⚡ Real-time story generation with token budget management
- ✍️ Prose-quality safeguards (chat-template enforcement + anti-"caveman English" output gate)

## Architecture

### Backend
- **FastAPI** - Modern async Python web framework
- **SQLAlchemy** - ORM for database management
- **SQL Server** - Primary database (via `pyodbc` + ODBC Driver 17 for SQL Server)
- **llama-cpp-python** - AI model loading and inference (local GGUF instruct models)
- **CUDA** - GPU acceleration for model inference (recommended)

### Two-server model

The backend runs as **two separate processes**:

| Process | File | Default port | Responsibility |
|---------|------|--------------|----------------|
| **Data server** | `data_server.py` (via `main.py`) | `8080` | REST API, auth, worlds, history, DB access, and serving AI settings over HTTP |
| **AI server** | `ai_server.py` (via `ai_main.py`) | `9000` | Loads the GGUF model with llama.cpp and generates story text |

The AI server is designed to run under **WSL2** (for CUDA) while the data server runs on **Windows**. Because WSL cannot reach SQL Server directly, the AI server fetches its settings over HTTP from the data server's `/settings/resolve` endpoint when `SETTINGS_REMOTE_URL` is set.

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
- **Python**: 3.10+ (recommended 3.10 for best compatibility)
- **Node.js**: 16+ and npm (for frontend)
- **CUDA**: Required for GPU acceleration of the AI server
- **GPU**: Recommended for local model inference (12GB+ VRAM suggested for a 14B Q5_K_M model)
- **RAM**: 16GB+ recommended
- **Storage**: 20GB+ free space for models
- **WSL2** (Windows): recommended for running the GPU AI server with CUDA

### Software Dependencies
- Git
- Python virtual environment (venv)
- **SQL Server** + **ODBC Driver 17 for SQL Server** (used by the data server via `pyodbc`)
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
The default database is **SQL Server**. Set the connection string via the `DATABASE_URL` environment variable (see `FastAPIAdventureInAI/config.py`):
```python
DATABASE_URL = "mssql+pyodbc://username:password@HOSTNAME/DATABASE?driver=ODBC+Driver+17+for+SQL+Server"
```
Prefer putting this in a `.env` file (copy from `.env.example`) rather than editing `config.py` directly.

#### Create Database Tables & Seed Initial Data
Run the setup script, which creates all tables and seeds the initial data in one step:
```bash
python setup_database.py
```

This will create default game ratings, pre-built worlds, AI directive settings, account levels, and an admin user.

> You can also run `python seed_data.py` on its own to (re)seed data once the tables exist.

## Download AI Model

The project uses a local **GGUF** model loaded with llama.cpp. The model path is configured via the `STORY_MODEL_PATH` environment variable (see `FastAPIAdventureInAI/config.py`).

Recommended model: **`Qwen2.5-14B Uncensored Instruct` (Q5_K_M GGUF)**. Any GGUF instruct model with a ChatML-compatible chat template will work.

Model-related settings (all read from env, with defaults in `config.py`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `STORY_MODEL_PATH` | `/home/dmin/models/Qwen2.5-14B_Uncensored_Instruct-Q5_K_M.gguf` | Absolute path to the GGUF file |
| `STORY_MODEL_CTX` | `32768` | Context window size (tokens) |
| `STORY_MODEL_GPU_LAYERS` | `-1` | GPU layers to offload (`-1` = all) |

The engine (`ai/services/ai_modeler_service.py`) forces `chat_format="chatml"` so instruct models are prompted with the correct template.

## How to Run

The full stack is **three processes**:

1. **Data server** (Windows) &mdash; REST API + database, port `8080`
2. **AI server** (WSL2 for CUDA) &mdash; GGUF model inference, port `9000`
3. **React client** &mdash; web UI, port `3000`

Start them in this order: **data server \u2192 AI server \u2192 client**. The AI server depends on the data server for its settings (`/settings/resolve`), and the client talks to both.

> All commands assume you are in the repository root unless noted. The backend package lives in the nested `FastAPIAdventureInAI/` folder.

### 1. Data Server (Windows / PowerShell)

Runs `data_server:app` via `main.py`. Needs access to SQL Server.

```powershell
cd FastAPIAdventureInAI
.\env\Scripts\Activate.ps1
python main.py
```

- Serves on `http://0.0.0.0:8080`
- Swagger UI: `http://localhost:8080/docs`
- Leave `SETTINGS_REMOTE_URL` **unset** here (this process is the DB source of truth).

Equivalent manual command:
```powershell
uvicorn data_server:app --host 0.0.0.0 --port 8080 --reload
```

### 2. AI Server (WSL2 / bash)

Runs `ai_server:app`. Loads the GGUF model on the GPU. Because WSL cannot reach SQL Server directly, point it at the Windows data server for settings.

```bash
cd /mnt/d/dev/source/repos/FastAPIAdventureInAI/FastAPIAdventureInAI
source .venv-wsl/bin/activate

# Tell the AI server where to fetch settings (use the Windows host LAN IP,
# NOT localhost \u2014 WSL\u2192Windows localhost forwarding does not work).
export SETTINGS_REMOTE_URL=\"http://192.168.1.12:8080\"
# Optional: override the model path if different from config.py
# export STORY_MODEL_PATH=\"/home/dmin/models/Qwen2.5-14B_Uncensored_Instruct-Q5_K_M.gguf\"

uvicorn ai_server:app --host 0.0.0.0 --port 9000
```

- Serves on `http://0.0.0.0:9000` (reachable from Windows as `http://localhost:9000`)
- On first start it loads the full model (watch for `[STORY ENGINE] Model loaded successfully`).
- You can also launch it with the helper entry point: `python ai_main.py`.

> **Windows-only (no WSL)?** You can run the AI server in the same Windows venv with `uvicorn ai_server:app --host 0.0.0.0 --port 9000`, and leave `SETTINGS_REMOTE_URL` unset so it reads the DB directly. CUDA support then depends on your Windows `llama-cpp-python` build.

### 3. React Client

```bash
cd adventure-client
npm install   # first run only
npm start
```

- Serves on `http://localhost:3000`
- The client's API/AI base URLs are configured in `adventure-client/src/config.js`. For local WSL testing, the AI URL should point to `http://localhost:9000`.

### Quick reference

| Process | Directory | Command | URL |
|---------|-----------|---------|-----|
| Data server | `FastAPIAdventureInAI/` | `python main.py` | http://localhost:8080 |
| AI server | `FastAPIAdventureInAI/` (WSL) | `uvicorn ai_server:app --host 0.0.0.0 --port 9000` | http://localhost:9000 |
| Client | `adventure-client/` | `npm start` | http://localhost:3000 |

## Usage

1. Open browser to `http://localhost:3000`
2. Login with the seeded admin account (if present) or register a user
3. Create a new game and start playing

## Configuration

Configuration is driven by environment variables (loaded from a `.env` file if present) with fallbacks in `FastAPIAdventureInAI/config.py`.

### Core settings (`config.py`)
```python
# Database (data server only)
DATABASE_URL = "mssql+pyodbc://username:password@HOSTNAME/DATABASE?driver=ODBC+Driver+17+for+SQL+Server"

# Auth
SECRET_KEY = "your-secret-key"          # Change in production!
ALGORITHM = "HS256"

# Server URLs
API_SERVER_URL = "http://localhost:8080"
AI_SERVER_URL  = "http://localhost:9000"

# AI model (AI server)
STORY_MODEL_PATH       = "/home/dmin/models/Qwen2.5-14B_Uncensored_Instruct-Q5_K_M.gguf"
STORY_MODEL_CTX        = 32768
STORY_MODEL_GPU_LAYERS = -1              # -1 = offload all layers to GPU

# Remote settings relay (AI server in WSL). Leave empty on the data server.
SETTINGS_REMOTE_URL = ""                 # e.g. http://192.168.1.12:8080
```

The React client reads its own base URLs from `adventure-client/src/config.js` (overridable with `REACT_APP_API_URL` / `REACT_APP_AI_URL`).

### AI Model & Generation Settings

Story token budgets and memory limits are stored in the database (`AIDirectiveSettings`) and served to the AI server via `GET /settings/resolve`. They can be managed through the dev app or seeded via `seed_data.py`; defaults also live in `aiadventureinpythonconstants.py`.

Generation sampling (temperature, `top_p`, `repeat_penalty`, etc.) is set in `ai/routers/root_router.py` and `ai/services/ai_modeler_service.py`. To keep prose fluent, the OpenAI-style `frequency_penalty`/`presence_penalty` are kept at `0.0` and only a gentle `repeat_penalty` is used. A prose-quality gate in `root_router.py` rejects telegraphic/run-on output before it is saved to history.

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
- **Virtual environment**: ensure it's activated and dependencies are installed before running either server.
- **`Can't open lib 'ODBC Driver 17 for SQL Server'`**: the ODBC driver is missing. Install it on the host running the **data server**. The AI server does not need it (it uses the HTTP settings relay).
- **AI server can't reach the data server from WSL**: use the Windows host's **LAN IP** in `SETTINGS_REMOTE_URL` (e.g. `http://192.168.1.12:8080`), not `localhost` \u2014 WSL\u2192Windows localhost forwarding does not work.
- **Client can't reach the AI server**: for local WSL testing point the client at `http://localhost:9000` (Windows\u2192WSL localhost forwarding does work).
- **CUDA OOM when loading the model**: lower `STORY_MODEL_CTX` (e.g. `16384`), reduce `STORY_MODEL_GPU_LAYERS`, or use a smaller/more-quantized GGUF.
- **Output is repetitive or broken ("caveman English")**: keep `frequency_penalty`/`presence_penalty` at `0.0` and start a fresh game \u2014 contaminated story history can steer the model back into bad prose.
- **Windows file-watch crash on reload**: do not place the WSL venv (`.venv-wsl`) inside the Windows-watched repo; the reloader chokes on Linux symlinks.
- **Ports in use**: change the port in `main.py` / `ai_main.py` or on the `uvicorn` command line.

## API Documentation
Once running backend, visit:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

## Security Notes
- Change `SECRET_KEY` and default passwords before production
- Use HTTPS and proper credentials in production

## License
Add your license here.
