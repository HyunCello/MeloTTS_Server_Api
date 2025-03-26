import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import torch
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from tts_manager import tts_model, TTSModel
from models import TTSRequest
from utils import cache_synthesize, get_resampler, audio_to_bytes

# Load environment variables
load_dotenv()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
WORKERS = int(os.getenv("WORKERS", 1))  # Reduce default workers to 1 to prevent memory issues
MAX_CACHE_SIZE = int(os.getenv("MAX_CACHE_SIZE", 2048))
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Initialize FastAPI app
app = FastAPI(title="MeloTTS API", description="API Server for MeloTTS Model", version="1.0")

# Initialize a ThreadPoolExecutor for handling blocking operations asynchronously
executor = ThreadPoolExecutor(max_workers=WORKERS)

@app.get("/speakers")
async def get_speaker_ids():
    return {"available_speakers": list(tts_model.speaker_ids.keys())}

@app.post("/language/switch")
async def switch_language(language_request: dict):
    """Switch the TTS model to a different language.
    
    Args:
        language_request (dict): Request with language field
        
    Returns:
        dict: Status message and available speakers for the new language
    """
    # Extract language from request
    if not isinstance(language_request, dict) or "language" not in language_request:
        language = language_request  # Try to use the raw input if it's a string
    else:
        language = language_request["language"]
    
    # Validate language
    valid_languages = ["EN", "ES", "FR", "ZH", "JP", "KR"]
    if language not in valid_languages:
        raise HTTPException(status_code=400, detail=f"Invalid language. Must be one of {valid_languages}")
    
    # Initialize new TTS model with the selected language
    global tts_model
    tts_model = TTSModel(language=language, device=DEVICE)
    
    return {
        "status": f"Switched to {language} language model",
        "available_speakers": list(tts_model.speaker_ids.keys())
    }

@app.post("/tts/generate", response_description="Generate and stream TTS audio")
async def generate_tts_audio(request: TTSRequest):
    """
    Generate TTS audio based on the provided request parameters and stream it to the client.
    
    Args:
        request (TTSRequest): The TTS generation request.
        
    Returns:
        StreamingResponse: Streamed WAV audio data.
    """
    # Validate speaker ID
    if request.voice_id not in tts_model.speaker_ids:
        raise HTTPException(status_code=400, detail="Invalid speaker ID")

    start_time = time.time()
    try:
        # Asynchronously perform synthesis to prevent blocking the event loop
        audio, sr = await asyncio.get_event_loop().run_in_executor(
            executor,
            cache_synthesize,
            request.text,
            request.voice_id,
            request.sdp_ratio,
            request.noise_scale,
            request.noise_scale_w,
            request.speed
        )

        # Resample if necessary
        if sr != request.sr:
            resampler = get_resampler(sr, request.sr)
            audio_tensor = torch.from_numpy(audio)
            audio_tensor = resampler(audio_tensor)
            audio = audio_tensor.cpu().numpy()
            sr = request.sr

        # Convert audio to bytes
        audio_bytes = audio_to_bytes(torch.from_numpy(audio), sr)

        generation_time = time.time() - start_time

        async def audio_generator():
            """Generator to stream audio in chunks."""
            chunk_size = 1024  # 1KB chunks
            for i in range(0, len(audio_bytes), chunk_size):
                yield audio_bytes[i:i+chunk_size]
                await asyncio.sleep(0)  # Yield control to event loop

        headers = {"generation_time_seconds": f"{generation_time:.3f}"}
        return StreamingResponse(audio_generator(), media_type="audio/wav", headers=headers)

    except Exception as e:
        # Handle any unexpected errors gracefully
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")

@app.on_event("shutdown")
def shutdown_event():
    """Handle shutdown events to clean up resources."""
    tts_model.close()
    executor.shutdown()

if __name__ == "__main__":
    # Run the Uvicorn server with optimized settings
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        workers=WORKERS,
        reload=False,  # Disable reload for production
        timeout_keep_alive=300,
        log_level="info",
        limit_concurrency=5,  # Limit concurrent requests
        timeout_graceful_shutdown=30  # Give more time for graceful shutdown
    )
