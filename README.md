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
- **PyTorch + Transformers** - AI model loading and inference
- **CUDA** - GPU acceleration for model inference

### Frontend
- **React** - UI framework
- **Axios** - API communication
- **CSS** - Custom styling

### Directory Structure
```
FastAPIAdventureInAI/
├── FastAPIAdventureInAI/          # Backend Python application
│   ├── business/                   # Business logic layer
│   │   ├── models/                 # Database models
│   │   ├── dtos/                   # Data transfer objects
│   │   ├── converters/             # Model-to-DTO converters
│   │   ├── schemas/                # API request/response schemas
│   │   └── game_service.py         # Game setup logic
│   ├── ai/                         # AI integration layer
│   │   ├── ai_settings.py          # AI configuration loader
│   │   ├── ai_client_requests.py   # AI server HTTP client
│   │   ├── schemas_ai_server.py    # AI request schemas
│   │   └── ai_helpers.py           # Story generation helpers
│   ├── routers/                    # API route handlers
│   ├── services/                   # Shared business services
│   ├── ai_server.py                # Standalone AI inference server
│   ├── main.py                     # FastAPI application entry
│   ├── seed_data.py                # Database seeding script
│   └── config.py                   # Configuration management
└── adventure-client/               # React frontend
    ├── src/
    │   ├── App.js                  # Main application component
    │   ├── Login.js                # Authentication
    │   ├── Game.js                 # Game interface
    │   ├── NewGame.js              # Game creation
    │   └── ManageWorlds.js         # World management
    └── public/
```

## Prerequisites

### System Requirements
- **Python**: 3.10+ (recommended 3.10 for best compatibility)
- **Node.js**: 16+ and npm
- **CUDA**: 11.8+ (for GPU acceleration)
- **GPU**: NVIDIA GPU with 8GB+ VRAM (for running the AI model)
- **RAM**: 16GB+ recommended
- **Storage**: 20GB+ free space for models

### Software Dependencies
- Git
- Python virtual environment (venv)
- Visual Studio Build Tools (Windows) or gcc/g++ (Linux)

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/VersacheX/FastAPIAdventureInAI.git
cd FastAPIAdventureInAI
```

### 2. Backend Setup

#### Create Python Virtual Environment
```bash
cd FastAPIAdventureInAI
python -m venv env
```

#### Activate Virtual Environment
**Windows (PowerShell):**
```powershell
.\env\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.\env\Scripts\activate.bat
```

**Linux/Mac:**
```bash
source env/bin/activate
```

#### Install Python Dependencies
```bash
pip install -r requirements.txt
```

**Note**: If you encounter CUDA/PyTorch issues, install PyTorch separately first:
```bash
# For CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

#### Configure Database
Edit `config.py` to set your database connection:
```python
# For SQLite (default)
DATABASE_URL = "sqlite:///./adventure.db"

# For PostgreSQL
# DATABASE_URL = "postgresql://user:password@localhost/adventure_db"

# For SQL Server
# DATABASE_URL = "mssql+pyodbc://user:password@server/database?driver=SQL+Server"
```

#### Create Database Tables
```bash
python -c "from dependencies import engine; from business.models import Base; Base.metadata.create_all(bind=engine)"
```

#### Seed Initial Data
```bash
python seed_data.py
```

This will create:
- Default game ratings (Family Friendly, Mature, Unrestricted)
- System worlds (Terminator Nexus, Mad Max Wasteland)
- AI directive settings (Basic and Elite tiers)
- Account levels
- Admin user (username: `admin`, password: `admin123`)

**⚠️ IMPORTANT**: Change the admin password after first login!

### 3. Frontend Setup

```bash
cd ../adventure-client
npm install
```

### 4. Download AI Model

The application uses **MythoMax-L2-13B-GPTQ** (or similar GPTQ models). Download and place in an accessible directory.

**Recommended model**: [TheBloke/MythoMax-L2-13B-GPTQ](https://huggingface.co/TheBloke/MythoMax-L2-13B-GPTQ)

Update the model path in `ai_server.py`:
```python
MODEL_NAME = "path/to/your/model/MythoMax-L2-13B-GPTQ"
```

## Running the Application

You need to run **three separate processes**:

### Terminal 1: AI Inference Server
```bash
cd FastAPIAdventureInAI
.\env\Scripts\Activate.ps1  # Activate venv
python ai_server.py
```
This starts the AI model server on `http://localhost:9000`

### Terminal 2: FastAPI Backend
```bash
cd FastAPIAdventureInAI
.\env\Scripts\Activate.ps1  # Activate venv
python main.py
```
This starts the API server on `http://0.0.0.0:8080`

### Terminal 3: React Frontend
```bash
cd adventure-client
npm start
```
This starts the development server on `http://localhost:3000`

## Usage

1. Open browser to `http://localhost:3000`
2. Login with:
   - **Username**: `admin`
   - **Password**: `admin123`
3. Create a new game:
   - Choose a world (Terminator Nexus or Mad Max Wasteland)
   - Select content rating
   - Enter player name and gender
4. Start playing!

## Configuration

### API Settings (`config.py`)
```python
SECRET_KEY = "your-secret-key-here"  # Change in production!
DATABASE_URL = "sqlite:///./adventure.db"
AI_SERVER_URL = "http://127.0.0.1:9000"
```

### AI Model Settings
Adjust token budgets and memory limits in `aiadventureinpythonconstants.py`:
```python
MAX_TOKENS = 4096                   # Model context window
RECENT_MEMORY_LIMIT = 12            # Recent history entries
TOKENIZE_THRESHOLD = 850            # Trigger compression at N tokens
TOKENIZED_HISTORY_BLOCK_SIZE = 230  # Tokens per compressed chunk
DEEP_MEMORY_MAX_TOKENS = 300        # Ultra-compressed history size
```

### Frontend Settings (`adventure-client/src/config.js`)
```javascript
export const API_URL = 'http://192.168.1.12:8080';  // Your API server address
```

## Memory Management System

The application uses a sophisticated three-tier memory compression system:

1. **Recent History** (uncompressed): Last 12-15 story entries, full text
2. **Tokenized Chunks** (compressed): Older entries summarized into ~230 token blocks
3. **Deep Memory** (ultra-compressed): Ancient history compressed to ~300 tokens

This ensures the AI always has relevant context while staying within the 4096 token model limit.

## Development

### Adding New Worlds
1. Edit `aiadventureinpythonconstants.py`
2. Add new entry to `STORY_SETUPS` dict:
```python
STORY_SETUPS = {
    "Your World Name": {
        "preface": "Opening scene description...",
        "world_tokens": "World lore and context..."
    }
}
```
3. Run `python seed_data.py` to add to database

### Adding API Endpoints
1. Create/edit router in `routers/`
2. Import and register in `main.py`:
```python
from routers import your_router
app.include_router(your_router.router)
```

### Database Migrations
When changing models:
1. Update models in `business/models/models.py`
2. Manually update database or use Alembic (not currently configured)

## Troubleshooting

### "ModuleNotFoundError"
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt` again

### "CUDA out of memory"
- Reduce `RECENT_MEMORY_LIMIT` in constants
- Use a smaller model
- Close other GPU-intensive applications

### "Port already in use"
- Change port in `main.py` (FastAPI) or `ai_server.py`
- Kill process using the port: `netstat -ano | findstr :8080`

### Frontend can't connect to backend
- Check `API_URL` in `adventure-client/src/config.js`
- Ensure CORS is configured correctly in `main.py`
- Verify both servers are running

### Database errors
- Delete `adventure.db` and recreate: `python seed_data.py`
- Check `DATABASE_URL` in `config.py`

## Security Notes

⚠️ **For Development Only**:
- Change `SECRET_KEY` in production
- Change default admin password immediately
- Use HTTPS in production
- Don't expose AI server publicly
- Use environment variables for secrets

## Performance Tips

1. **GPU Memory**: The AI model needs ~7-8GB VRAM
2. **First Request**: Model loading takes 30-60 seconds on first AI call
3. **Response Time**: Story generation takes 5-15 seconds depending on GPU
4. **Token Budget**: Monitor console logs for token usage warnings

## API Documentation

Once running, visit:
- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`

## License

[Add your license here]

## Contributing

[Add contribution guidelines]

## Credits

- Built with FastAPI, React, and PyTorch
- AI Model: MythoMax-L2-13B-GPTQ by TheBloke
- GPTQ quantization by AutoGPTQ

## Support

For issues and questions:
- GitHub Issues: [Repository Issues](https://github.com/VersacheX/FastAPIAdventureInAI/issues)

## Suggestions & Contact

For suggestions, feedback, or questions, please email:

**lulhamjessie@aol.com**

I welcome all ideas to improve the project!

## Author

Project created and maintained by Jessie Lulham.

For suggestions or feedback, email: lulhamjessie@aol.com

## PyTorch & CUDA Setup

This project uses PyTorch with CUDA 12.6 for GPU acceleration.

**Recommended installation for CUDA 12.6:**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

If you use a different CUDA version, visit the [PyTorch Get Started page](https://pytorch.org/get-started/locally/) for the correct installation command.
