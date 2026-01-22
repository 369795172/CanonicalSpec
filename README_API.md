# Canonical API Server

FastAPI server for Canonical Spec Manager frontend.

## Quick Start

### 1. Install Dependencies

```bash
cd /Users/marvi/AndroidStudioProjects/canonical
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Start API Server

```bash
# Method 1: Using the script
./start_api.sh

# Method 2: Direct command
uvicorn canonical.api:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Start Frontend

```bash
cd /Users/marvi/AndroidStudioProjects/canonical_frontend
npm run dev
```

## API Endpoints

- **Health Check**: `GET /api/v1/system/health`
- **List Features**: `GET /api/v1/features`
- **Get Feature**: `GET /api/v1/features/{feature_id}`
- **Create Feature**: `POST /api/v1/run`
- **Transcribe Audio**: `POST /api/transcribe` (placeholder)

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Configuration

Make sure your `.env` file contains:
- `CANONICAL_LLM_API_KEY` - OpenAI API key for LLM compiler
- `CANONICAL_FEISHU_APP_ID` - Feishu app ID (for publishing)
- `CANONICAL_FEISHU_APP_SECRET` - Feishu app secret
- `CANONICAL_FEISHU_BASE_TOKEN` - Feishu base token
- `CANONICAL_FEISHU_TABLE_ID` - Feishu table ID

## Voice Transcription

The `/api/transcribe` endpoint is currently a placeholder. To enable voice transcription:

1. Add OpenAI API key to `.env`:
   ```
   OPENAI_API_KEY=your_key_here
   ```

2. Update `canonical/api.py` to use OpenAI Whisper API (see TODO comments in the code)
