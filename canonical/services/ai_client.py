"""
AI Client for AI Builder Space platform.
Provides audio transcription functionality.
"""
import io
from typing import Optional, Dict, Any
import httpx


class AIClient:
    """AI Builder Space client for audio transcription."""
    
    def __init__(self, token: str, base_url: str = "https://space.ai-builders.com/backend/v1"):
        """
        Initialize AI Builder Space client.
        
        Args:
            token: AI Builder Space API token
            base_url: API base URL (default: AI Builder Space endpoint)
        """
        if not token:
            raise ValueError("AI Builder Space token is required")
        
        self.token = token
        self.base_url = base_url
    
    async def transcribe_audio(
        self,
        audio_file: bytes,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio using AI Builder Space transcription API.
        
        Args:
            audio_file: Audio file data as bytes
            language: Optional BCP-47 language code hint (e.g., 'en', 'zh-CN')
            
        Returns:
            Transcription response with text and metadata
            
        Raises:
            Exception: If transcription fails
        """
        try:
            # Create a file-like object from bytes
            audio_io = io.BytesIO(audio_file)
            
            # Prepare multipart form data
            files = {
                "audio_file": ("audio.webm", audio_io, "audio/webm")
            }
            data = {}
            if language:
                data["language"] = language
            
            # Use httpx to make multipart/form-data request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers={
                        "Authorization": f"Bearer {self.token}"
                    },
                    files=files,
                    data=data,
                    timeout=60.0
                )
                
                if response.status_code != 200:
                    raise Exception(f"Transcription failed: {response.text}")
                
                result = response.json()
                return result
            
        except Exception as e:
            print(f"Audio transcription failed: {str(e)}")
            raise Exception(f"Transcription failed: {str(e)}")
