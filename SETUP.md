# First-Time Setup Guide

This guide will help you get FastAPI Adventure in AI running from scratch.

## Quick Start (Automated)

### Windows
```bash
cd FastAPIAdventureInAI
python -m venv env
.\env\Scripts\activate.ps1
pip install -r requirements.txt
python quick_setup.bat
```

### Linux/Mac
```bash
cd FastAPIAdventureInAI
python -m venv env
source env/bin/activate
pip install -r requirements.txt
chmod +x quick_setup.sh
./quick_setup.sh
```

## Manual Setup (Step-by-Step)

### 1. System Requirements Check

Before starting, ensure you have:
- [ ] Python 3.10 or higher installed
- [ ] Node.js 16+ and npm installed
- [ ] NVIDIA GPU with 8GB+ VRAM
- [ ] CUDA 11.8 or 12.1 installed
- [ ] 20GB+ free disk space
- [ ] 16GB+ RAM

Verify installations:
```bash
python --version    # Should be 3.10+
node --version      # Should be 16+
nvidia-smi          # Should show your GPU
```

### 2. Clone Repository

```bash
git clone https://github.com/VersacheX/FastAPIAdventureInAI.git
cd FastAPIAdventureInAI
```

### 3. Backend Setup

#### A. Create Virtual Environment

**Windows (PowerShell):**
```powershell
cd FastAPIAdventureInAI
python -m venv env
.\env\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
cd FastAPIAdventureInAI
python -m venv env
source env/bin/activate
```

#### B. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**If you get CUDA/PyTorch errors:**
```bash
# For CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Then install remaining requirements
pip install -r requirements.txt
```

#### C. Configure Application

1. **Edit `config.py`** (if needed):
   - Default uses SQLite (no changes needed)
   - For PostgreSQL/MySQL, update `DATABASE_URL`
   - Change `SECRET_KEY` for production

2. **Edit `ai_server.py`** - Set your model path:
   ```python
   MODEL_NAME = "path/to/your/MythoMax-L2-13B-GPTQ"
   ```

#### D. Initialize Database

**Option 1: Automated (Recommended)**
```bash
python setup_database.py
```

**Option 2: Manual**
```bash
# Create tables
python -c "from dependencies import engine; from business.models import Base; Base.metadata.create_all(bind=engine)"

# Seed data
python seed_data.py
```

Expected output:
```
Created GameRating: Family Friendly
Created GameRating: Mature
Created GameRating: Unrestricted
Created World: Terminator Nexus
Created World: Mad Max Wasteland
Created Basic AI settings (ID=1)
Created Elite AI settings (ID=2)
Created Basic account level
Created Elite account level
Created admin user (username: admin, password: admin123)
```

### 4. Frontend Setup

```bash
cd ../adventure-client
npm install
```

If you get errors, try:
```bash
npm install --legacy-peer-deps
```

### 5. Download AI Model

You need a GPTQ quantized model. Recommended:

**MythoMax-L2-13B-GPTQ** by TheBloke:
```bash
# Using git-lfs (recommended)
git lfs install
git clone https://huggingface.co/TheBloke/MythoMax-L2-13B-GPTQ

# Or download manually from:
# https://huggingface.co/TheBloke/MythoMax-L2-13B-GPTQ
```

Update `ai_server.py` with the model path:
```python
MODEL_NAME = "/path/to/MythoMax-L2-13B-GPTQ"
```

### 6. Start the Application

You need **3 terminals running simultaneously**:

#### Terminal 1: AI Server
```bash
cd FastAPIAdventureInAI
.\env\Scripts\Activate.ps1  # Windows
# source env/bin/activate     # Linux/Mac
python ai_server.py
```

Wait for: `"Model loaded successfully"` (30-60 seconds)

#### Terminal 2: API Server
```bash
cd FastAPIAdventureInAI
.\env\Scripts\Activate.ps1  # Windows
# source env/bin/activate     # Linux/Mac
python main.py
```

Wait for: `"Application startup complete"`

#### Terminal 3: Frontend
```bash
cd adventure-client
npm start
```

Browser should auto-open to `http://localhost:3000`

### 7. First Login

1. Open browser to `http://localhost:3000`
2. Login with:
   - **Username**: `admin`
   - **Password**: `admin123`
3. **⚠️ IMPORTANT**: Change password immediately!

### 8. Create Your First Game

1. Click "New Game"
2. Choose a world (Terminator Nexus or Mad Max Wasteland)
3. Select content rating
4. Enter your character name
5. Choose gender
6. Click "Create"
7. Start playing!

## Troubleshooting

### "Virtual environment activation fails"

**Windows PowerShell** - Enable script execution:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "CUDA out of memory"

Your GPU doesn't have enough VRAM. Try:
1. Close other GPU applications
2. Use a smaller model (7B instead of 13B)
3. Reduce memory limits in `aiadventureinpythonconstants.py`

### "Module not found" errors

Ensure virtual environment is activated:
```bash
# You should see (env) at the start of your prompt
# If not, activate it again:
.\env\Scripts\Activate.ps1  # Windows
source env/bin/activate     # Linux
```

### "Port already in use"

Kill the process or change the port:

**Find and kill process (Windows):**
```powershell
netstat -ano | findstr :8080
taskkill /PID <PID> /F
```

**Change port** in `main.py`:
```python
uvicorn.run(app, host="0.0.0.0", port=8081)  # Changed from 8080
```

### Frontend can't connect to API

1. Check `adventure-client/src/config.js`:
   ```javascript
   export const API_URL = 'http://localhost:8080';  // Use localhost for local dev
   ```

2. Ensure API server is running (check Terminal 2)

3. Check browser console for CORS errors

### Database errors

**Reset database:**
```bash
# Delete database file
rm adventure.db  # Linux/Mac
del adventure.db # Windows

# Recreate
python setup_database.py
```

### AI model won't load

1. Check model path in `ai_server.py`
2. Ensure model files exist
3. Check GPU is available: `nvidia-smi`
4. Verify CUDA version matches PyTorch installation

## Verification Checklist

Before reporting issues, verify:

- [ ] Virtual environment is activated
- [ ] All dependencies installed: `pip list`
- [ ] Database created: `adventure.db` file exists
- [ ] Admin user exists: `python -c "from dependencies import SessionLocal; from business.models import User; db = SessionLocal(); print(db.query(User).filter_by(username='admin').first())"`
- [ ] AI server responds: `curl http://localhost:9000/health` (if you added health endpoint)
- [ ] API server responds: `curl http://localhost:8080/docs`
- [ ] Frontend builds: No errors in Terminal 3

## Next Steps

Once everything is running:

1. **Read the README.md** for full documentation
2. **Change admin password**
3. **Create custom worlds** (edit `aiadventureinpythonconstants.py`)
4. **Adjust AI settings** for your hardware
5. **Explore the API docs** at `http://localhost:8080/docs`

## Getting Help

If you're stuck:

1. Check the error message carefully
2. Search issues on GitHub
3. Check console logs in all 3 terminals
4. Review browser console (F12)
5. Open an issue with:
   - Your OS and Python version
   - Full error message
   - Steps to reproduce

## Production Deployment

**WARNING**: This setup is for development only!

For production:
- [ ] Change `SECRET_KEY` in `config.py`
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable HTTPS
- [ ] Use proper password hashing salt
- [ ] Set up reverse proxy (nginx)
- [ ] Use environment variables for secrets
- [ ] Enable API rate limiting
- [ ] Set up logging and monitoring
- [ ] Don't expose AI server publicly

Refer to FastAPI deployment guide: https://fastapi.tiangolo.com/deployment/
