"""
backend/state.py — Central Backend State & Background Worker Layer
==================================================================
This module serves as the central nervous system for the FastAPI backend.
It holds all shared in-memory variables used by background threads, manages
WebSocket notifications and Telegram/TTS alerts, and runs the background 
video ingestion task thread.

By centralizing state and utilities here, we prevent circular imports between 
our FastAPI route modules (auth.py, media.py, queries.py, alerts.py) and the 
main server entrypoint.

Coordination:
- Used by: backend/main.py, backend/routes/*.py
"""

import os
import sys
import time
import asyncio
import threading
import requests
import cv2
import dotenv
from PIL import Image
from fastapi import WebSocket

# Insert workspace root to sys.path so we can import model modules correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.pipelineY import OfflineVideoPipeline

# Load environmental variables from the root .env file
dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)


# ──────────────────────────────────────────────────────────────────────────
# 1. Shared In-Memory Backend State
# ──────────────────────────────────────────────────────────────────────────

# Store processed frame buffers (bytes) for live streaming (key: source_id, value: jpg bytes)
latest_frames: dict[str, bytes] = {}

# Keep track of stream dimensions (key: source_id, value: 'portrait' | 'landscape')
stream_orientations: dict[str, str] = {}

# Record active camera feed sources (key: source_id, value: stream URL)
active_stream_info: dict[str, str] = {}

# Track processing state of all uploaded videos & camera streams (key: source_id, value: 'processing' | 'completed' | 'error: ...')
video_processing_status: dict[str, str] = {}

# Manage asyncio events to trigger frame updates on the websocket (key: source_id, value: asyncio.Event)
new_frame_events: dict[str, asyncio.Event] = {}

# Record the last cooldown timestamp for each active rule to prevent alert spamming
rule_last_triggered: dict[int, float] = {}

# [BUG FIX] Track suspect location history to detect transitions between cameras (key: rule_text, value: last_seen_camera_id)
global_suspect_tracker: dict[str, str] = {}

class TrackedValue:
    """Helper container to hold the active video/camera identifier across threads."""
    def __init__(self, value: str):
        self.value = value

last_active_source = TrackedValue("")

# Reference to the main running asyncio loop, set during FastAPI startup
main_loop: asyncio.AbstractEventLoop | None = None


# ──────────────────────────────────────────────────────────────────────────
# 2. WebSocket Real-Time Alert Manager
# ──────────────────────────────────────────────────────────────────────────
class ConnectionManager:
    """
    Manages active client connections to our backend WebSocket alert channel.
    This enables real-time push notifications (e.g. popping up security alerts in the UI).
    """
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accepts and registers a new WebSocket client connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"🔌 [WebSocket] Client connected. Total active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Deregisters a disconnected WebSocket client."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"🔌 [WebSocket] Client disconnected. Active connections remaining: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """
        [BUG FIX] Broadcasts a message to all active WebSocket clients.
        Used to stream live security alerts directly to the frontend interface.
        """
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                # If a client connection is broken/closed, ignore and proceed
                pass

notifier = ConnectionManager()


# ──────────────────────────────────────────────────────────────────────────
# 3. ML Engine Initialization
# ──────────────────────────────────────────────────────────────────────────
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ [State] CRITICAL WARNING: GEMINI_API_KEY could not be loaded!")
    ml_engine = None
else:
    print(f"✅ [State] GEMINI_API_KEY loaded. ML Engine ready.")
    # Initialize the modularized ML pipeline
    ml_engine = OfflineVideoPipeline(api_key=api_key, collection_name="cctv_main_stream")


# ──────────────────────────────────────────────────────────────────────────
# 4. Notification & Alerts Core Utilities
# ──────────────────────────────────────────────────────────────────────────

def send_telegram_alert(text: str, image_path: str = None):
    """
    Dispatches a security notification containing alert text and optionally
    the matching CCTV frame image to the operator's configured Telegram channel.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        return  # Integration not configured by user
        
    try:
        if image_path and os.path.exists(image_path):
            # Send alert with CCTV capture image
            with open(image_path, "rb") as image_file:
                res = requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                    data={"chat_id": chat_id, "caption": text},
                    files={"photo": image_file}
                )
            print(f"📡 [Telegram] Photo Alert dispatched. Status: {res.status_code}")
        else:
            # Fallback to plain text message
            res = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data={"chat_id": chat_id, "text": text}
            )
            print(f"📡 [Telegram] Text Alert dispatched. Status: {res.status_code}")
    except Exception as e:
        print(f"❌ [Telegram] Failed to dispatch alert: {e}")


def clean_text_for_speech(text: str) -> str:
    """
    Strips Markdown markers and headers from text reports to generate
    clean, natural-sounding sentences for text-to-speech engine conversion.
    """
    import re
    text = text.replace("**", "").replace("*", "")
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'^\s*[-•+]\s*', '', text, flags=re.MULTILINE)
    text = text.replace("\n", " ").strip()
    return text


def speak_alarm(phrase: str):
    """
    Converts text instructions into audible alarms using offline pyttsx3.
    Runs in a detached daemon thread to prevent freezing the FastAPI request loops.
    """
    def _speak():
        try:
            clean_phrase = clean_text_for_speech(phrase)
            print("🤖 [Voice Alarm] Speaking notification offline.")
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 160) 
            engine.say(clean_phrase)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"❌ [Voice Alarm] Offline speech error: {e}")

    threading.Thread(target=_speak, daemon=True).start()


# ──────────────────────────────────────────────────────────────────────────
# 5. Background Thread Worker Task
# ──────────────────────────────────────────────────────────────────────────

def process_video_task(file_path: str, source_id: str, collection_name: str = "cctv_main_stream"):
    """
    Background worker thread function that feeds incoming video frames to the 
    ML Engine (OfflineVideoPipeline) for preprocessing and vector storage.
    
    Coordinates with `model/pipelineY.py` via callbacks to capture live frame 
    buffers to allow real-time stream viewing in the dashboard UI.
    """
    print(f"🎯 [Worker Thread] Starting ingestion process for '{source_id}'...")
    video_processing_status[source_id] = "processing"
    
    def frame_update_callback(frame):
        """Callback invoked by ML engine on every processed video frame."""
        if frame is None:
            return
        try:
            h, w = frame.shape[:2]
            stream_orientations[source_id] = "portrait" if h > w else "landscape"
            
            # Encode NumPy BGR frame to JPEG byte stream
            _, buffer = cv2.imencode('.jpg', frame)
            latest_frames[source_id] = buffer.tobytes()
            
            # Notify the async stream generators that a new frame is ready
            if source_id in new_frame_events:
                event = new_frame_events[source_id]
                global main_loop
                if main_loop and not main_loop.is_closed():
                    main_loop.call_soon_threadsafe(event.set)
        except Exception as e:
            print(f"❌ [Worker Thread] Callback frame update failed for '{source_id}': {e}")

    active_stream_info[source_id] = file_path 
    
    try:
        if ml_engine:
            ml_engine.ingest_video(
                video_path=file_path, 
                source_id=source_id, 
                collection_name=collection_name, 
                on_frame=frame_update_callback
            )
            video_processing_status[source_id] = "completed"
            print(f"🏁 [Worker Thread] Ingestion successful for '{source_id}'.")
        else:
            print(f"❌ [Worker Thread] Ingestion failed: ML Engine is unavailable.")
            video_processing_status[source_id] = "error: ML Engine not loaded"
             
        # Cleanup uploaded local temporary files once database storage is complete
        if not file_path.startswith("http") and os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        video_processing_status[source_id] = f"error: {str(e)}"
        print(f"❌ [Worker Thread] Ingestion crash on '{source_id}': {e}")
