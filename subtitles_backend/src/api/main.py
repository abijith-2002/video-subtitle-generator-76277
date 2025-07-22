import os
import uuid
import shutil
import subprocess
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from dotenv import load_dotenv

# PUBLIC_INTERFACE
def get_env_variable(key: str, default: Optional[str] = None) -> str:
    """
    Get an environment variable or raise error if not found and no default is provided.
    Used for secret keys or API keys for transcription service.
    """
    value = os.environ.get(key, default)
    if value is None:
        raise EnvironmentError(f"Missing required environment variable {key}")
    return value

# Load .env variables
load_dotenv()

app = FastAPI(
    title="Subtitles Backend",
    description="API for uploading videos, extracting audio, transcribing to subtitles (.srt), and downloading .srt files.",
    version="1.0.0",
    openapi_tags=[
        {"name": "health", "description": "Health check endpoint"},
        {"name": "upload", "description": "Upload and process video files"},
        {"name": "subtitles", "description": "Subtitle download endpoints"},
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.abspath(os.getenv("UPLOAD_DIR", "uploaded_videos"))
SUBTITLE_DIR = os.path.abspath(os.getenv("SUBTITLE_DIR", "generated_subtitles"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SUBTITLE_DIR, exist_ok=True)

# PUBLIC_INTERFACE
@app.get("/", tags=["health"], summary="Health Check", description="Check API health status")
def health_check():
    """
    Returns 200 OK status if the server is running.
    """
    return {"status": "Healthy"}

class UploadResponse(BaseModel):
    """Response model for file upload."""
    video_id: str = Field(..., description="Unique identifier for the uploaded video")

class SubtitleResponse(BaseModel):
    """Response model for subtitle file download link."""
    srt_url: str = Field(..., description="URL to download generated subtitle file")

def extract_audio(video_path: str, audio_path: str):
    """
    Extract audio from video using ffmpeg.
    Expects ffmpeg to be installed in the system.
    """
    command = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vn',  # no video
        '-acodec', 'pcm_s16le',
        '-ar', '16000',  # 16kHz (required for some STT engines)
        '-ac', '1',  # mono
        audio_path
    ]
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Audio extraction failed: {e.stderr.decode()}")

def transcribe_audio_whisper(audio_path: str) -> str:
    """
    Transcribe audio using OpenAI Whisper (local or API).
    This uses the openai-whisper library, or an external API if configured via env.
    """
    whisper_api_key = os.environ.get("OPENAI_API_KEY")
    try:
        import openai
    except ImportError:
        raise RuntimeError("openai python library is required. Please install openai.")

    openai.api_key = whisper_api_key

    # Using direct whisper model via OpenAI API (not local model)
    with open(audio_path, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
    # transcript is a JSON object with 'text' field
    return transcript['text']

def split_text_to_phrases(text: str, max_words: int = 8):
    """Split string into phrases at most max_words long for subtitle segmentation."""
    words = text.split()
    phrases = []
    phrase = []
    for word in words:
        phrase.append(word)
        if len(phrase) >= max_words:
            phrases.append(' '.join(phrase))
            phrase = []
    if phrase:
        phrases.append(' '.join(phrase))
    return phrases

def create_srt_from_text(text: str, srt_path: str, num_phrases: int = None):
    """
    Given full transcript text, generate a simple SRT file.
    This uses naive timing (not accurate to speech, for demo purposes).
    """
    phrases = split_text_to_phrases(text)
    num_phrases = num_phrases or len(phrases)
    # Assign fixed duration per phrase (e.g., 3 seconds/phrase); total duration = num_phrases * 3s
    phrase_duration = 3
    lines = []
    for i, phrase in enumerate(phrases):
        idx = i + 1
        start_s = i * phrase_duration
        end_s = (i + 1) * phrase_duration
        start = f"{start_s//3600:02}:{(start_s%3600)//60:02}:{start_s%60:02},000"
        end = f"{end_s//3600:02}:{(end_s%3600)//60:02}:{end_s%60:02},000"
        lines.append(f"{idx}")
        lines.append(f"{start} --> {end}")
        lines.append(phrase)
        lines.append("")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def cleanup_files(video_path: str, audio_path: str):
    try:
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception:
        pass

# PUBLIC_INTERFACE
@app.post(
    "/upload/",
    response_model=UploadResponse,
    tags=["upload"],
    summary="Upload Video for Subtitle Generation",
    description="Uploads a video file and processes it asynchronously. Returns a video_id to retrieve subtitles later.",
)
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video file, extract audio, transcribe, and generate subtitles.
    Returns a video ID for fetching subtitles later.
    """
    allowed_video_types = ["video/mp4", "video/avi", "video/x-matroska", "video/quicktime", "video/mpeg"]
    if file.content_type not in allowed_video_types:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Unsupported video format")

    video_id = str(uuid.uuid4())
    video_ext = file.filename.split('.')[-1]
    video_filename = f"{video_id}.{video_ext}"
    video_path = os.path.join(UPLOAD_DIR, video_filename)

    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    audio_path = os.path.join(UPLOAD_DIR, f"{video_id}.wav")
    srt_path = os.path.join(SUBTITLE_DIR, f"{video_id}.srt")

    try:
        # 1. Extract Audio
        extract_audio(video_path, audio_path)
        # 2. Transcribe Audio
        transcript = transcribe_audio_whisper(audio_path)
        # 3. Generate SRT
        create_srt_from_text(transcript, srt_path)
    except Exception as exc:
        cleanup_files(video_path, audio_path)
        raise HTTPException(status_code=500, detail=f"Subtitle generation failed: {exc}")

    cleanup_files(video_path, audio_path)
    return {"video_id": video_id}

# PUBLIC_INTERFACE
@app.get(
    "/subtitles/{video_id}/",
    response_model=SubtitleResponse,
    tags=["subtitles"],
    summary="Download generated .srt subtitle file",
    description="Download the generated .srt subtitle file for a video, given its video_id.",
)
async def get_subtitle_file(video_id: str):
    """
    Returns URL to download the generated .srt subtitle file.
    """
    srt_file = os.path.join(SUBTITLE_DIR, f"{video_id}.srt")
    if not os.path.exists(srt_file):
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Subtitle file not found for requested video")
    return {"srt_url": f"/subtitles/{video_id}/download"}

# PUBLIC_INTERFACE
@app.get(
    "/subtitles/{video_id}/download",
    summary="Download the raw .srt subtitle file",
    tags=["subtitles"],
    description="Triggers a raw file download of the .srt subtitle file.",
    responses={
        200: {
            "content": {"application/x-subrip": {}},
            "description": "Subtitle file download"
        }
    }
)
async def download_srt_file(video_id: str):
    """
    Download .srt subtitle file for video.
    """
    srt_file = os.path.join(SUBTITLE_DIR, f"{video_id}.srt")
    if not os.path.exists(srt_file):
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Subtitle file not found for this video")
    return FileResponse(srt_file, media_type="application/x-subrip", filename=f"{video_id}.srt")


# PUBLIC_INTERFACE
@app.get("/config/example-env", tags=["health"], summary="Show required environment variables")
def show_config_env():
    """
    Returns a list of required environment variables.
    """
    return {
        "UPLOAD_DIR": "Path for uploaded videos (optional; default: uploaded_videos)",
        "SUBTITLE_DIR": "Path for generated subtitles (optional; default: generated_subtitles)",
        "OPENAI_API_KEY": "Your OpenAI Whisper API key for audio transcription (required)",
    }

