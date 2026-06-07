"""
backend/routes/media.py — Media Router
========================================
Manages incoming camera livestreams, local video file uploads, status tracking, 
and streams MJPEG frames directly to the frontend HTML Canvas components.

Coordination:
- Used by: backend/main.py (registered as router).
- Relies on: backend/state.py (for sharing frame buffers and thread orchestration).
"""

import os
import cv2
import shutil
import asyncio
import threading
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

import backend.state as state

router = APIRouter(prefix="/api/media", tags=["Media Operations"])


# ──────────────────────────────────────────────────────────────────────────
# 1. Pydantic Models
# ──────────────────────────────────────────────────────────────────────────

class StreamConfig(BaseModel):
    stream_url: str
    source_name: str = "cam_1"

class LivestreamRequest(BaseModel):
    streams: List[StreamConfig]


# ──────────────────────────────────────────────────────────────────────────
# 2. Media Route Endpoints
# ──────────────────────────────────────────────────────────────────────────

@router.get("/status")
async def check_processing_status():
    """
    Checks the status of all active ingestion threads in the system.
    Returns status: 'processing', 'completed', 'failed', or 'idle'.
    """
    print(f"[Media Router] Querying status: {state.video_processing_status}")
    if not state.video_processing_status: 
        return {"status": "idle", "raw_status": {}}
        
    statuses = list(state.video_processing_status.values())
    if "processing" in statuses: 
        return {"status": "processing", "raw_status": state.video_processing_status}
    elif "completed" in statuses: 
        return {"status": "completed", "raw_status": state.video_processing_status}
        
    for s in statuses:
        if isinstance(s, str) and s.startswith("error"): 
            return {"status": "failed", "raw_status": state.video_processing_status}
            
    return {"status": "idle", "raw_status": state.video_processing_status}


@router.post("/livestream")
async def start_livestream(req: LivestreamRequest):
    """
    Launches asynchronous camera decoding threads for up to 3 live RTSP/HTTP streams.
    """
    print(f"[Media Router] Starting live streams: {[c.source_name for c in req.streams]}")
    active_streams = req.streams[:3]  # Limit to 3 concurrent streams for resource saving
    
    for config in active_streams:
        print(f"🚀 [Media Router] Launching ingestion thread for stream: {config.source_name}")
        # Run process_video_task inside a background thread so FastAPI request is not blocked
        thread = threading.Thread(
            target=state.process_video_task, 
            args=(config.stream_url, config.source_name, "live_cctv_stream"),
            daemon=True
        )
        thread.start()
         
    if active_streams:
        state.last_active_source.value = active_streams[-1].source_name
         
    return {"status": "success", "message": f"Successfully tracing {len(active_streams)} camera streams!"}


@router.get("/stream/{source_id}")
async def get_video_stream(source_id: str):
    """
    Streams JPEG buffers as a multipart/x-mixed-replace boundary feed.
    This can be direct-linked in HTML <img src="..."> tags to display real-time video.
    """
    # Create frame event lock for the stream if not already allocated
    if source_id not in state.new_frame_events:
        state.new_frame_events[source_id] = asyncio.Event()
    
    event = state.new_frame_events[source_id]

    async def frame_generator():
        while True:
            # Wait until a new frame is decoded by cv2 and set by the thread callback
            await event.wait()
            event.clear()
            
            frame_bytes = state.latest_frames.get(source_id)
            if frame_bytes:
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/orientation/{source_id}")
async def get_stream_orientation(source_id: str):
    """
    Returns orientation ('portrait' | 'landscape') of the stream.
    Used by the frontend to dynamically style aspect ratios on canvas layouts.
    """
    return {"orientation": state.stream_orientations.get(source_id, "landscape")}


@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """
    Saves an uploaded CCTV MP4 video file and runs a background ingestion thread
    to extract, index, and store CLIP embeddings in the uploaded_vault vector database.
    """
    print(f"[Media Router] Inbound video upload: {file.filename}")
    save_dir = "./data/videos"
    os.makedirs(save_dir, exist_ok=True)
    
    safe_filename = os.path.basename(file.filename)
    file_path = os.path.join(save_dir, safe_filename)
    print(f"📥 [Media Router] Writing chunks to: {file_path}")
    
    # Write chunks asynchronously to avoid running out of RAM on large uploads
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            buffer.write(chunk)
            
    if os.path.getsize(file_path) == 0:
        return {"status": "error", "message": "Failed to save file. File is empty."}
        
    print(f"✅ [Media Router] Save successful. File size: {os.path.getsize(file_path)} bytes")
        
    video_title = os.path.splitext(safe_filename)[0]
    state.last_active_source.value = video_title
    state.video_processing_status[video_title] = "processing"

    print(f"🚀 [Media Router] Launching ingestion thread for video: {video_title}")
    thread = threading.Thread(
        target=state.process_video_task, 
        args=(file_path, video_title, "uploaded_vault"),
        daemon=True
    )
    thread.start()
        
    return {"status": "processing", "message": "Video successfully saved. Processing started."}
