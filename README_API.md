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
- **Transcribe Audio**: `POST /api/v1/transcribe`

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
- `CANONICAL_AI_BUILDER_TOKEN` - AI Builder Space API token (for voice transcription, optional)

## Voice Transcription

The `/api/v1/transcribe` endpoint uses AI Builder Space API for audio transcription. To enable voice transcription:

1. Get your AI Builder Space API token
2. Add the token to `.env`:
   ```
   CANONICAL_AI_BUILDER_TOKEN=your_token_here
   ```
3. Restart the API server

The endpoint accepts audio files in WebM format and returns transcribed text along with detected language and confidence score.
