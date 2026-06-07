"""
backend/routes/queries.py — Query & Surveillance Search Router
==============================================================
Manages visual and natural language queries submitted by security operators.
Includes the main search endpoints, cross-camera timeline trace ("Detective Mode"),
and reverse suspect visual search via face/mugshot uploads.

Guardrails:
- All search routes are intercept-vetted by ArmorIQ Supervisor (backend/armoriq.py)
  to ensure operator compliance with privacy laws and demographic regulations.

Coordination:
- Used by: backend/main.py (registered as router).
- Relies on: backend/state.py (for ml_engine and active state references).
"""

import os
import shutil
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import APIRouter, UploadFile, File, Form, Depends

from backend.database import get_db
import backend.models as models
import backend.state as state
from backend.armoriq import armoriq_supervisor

router = APIRouter(prefix="/api", tags=["Queries & Search Operations"])


# ──────────────────────────────────────────────────────────────────────────
# 1. Pydantic Models
# ──────────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str


# ──────────────────────────────────────────────────────────────────────────
# 2. Query Route Endpoints
# ──────────────────────────────────────────────────────────────────────────

@router.post("/query")
async def manual_query(req: QueryRequest, db: Session = Depends(get_db)):
    """
    Operator text query. Performs a semantic search for objects/events on the active feed.
    """
    print(f"[Query Router] POST /api/query - Query: '{req.query}'")
    if not state.ml_engine: 
        print("[Query Router] Warning: ML Engine not loaded.")
        return {"response": "Warning: ML Engine not loaded."}
        
    try:
        source_id = state.last_active_source.value
        if not source_id:
             return {"status": "error", "message": "No active video or stream found."}
             
        # 🛡️ --- ArmorIQ Privacy Guardrail Intercept ---
        armoriq_result = armoriq_supervisor.evaluate_request(req.query, context=source_id)
        if armoriq_result["status"] == "blocked":
            return armoriq_result
        # ----------------------------------------------
             
        is_live = source_id in state.active_stream_info and state.active_stream_info[source_id].startswith("http")
        print(f"🕵️ [Query Router] Searching '{req.query}' in {'LIVE' if is_live else 'UPLOADED'} (Source: {source_id})")
        
        # Query the orchestrated ML engine
        result = state.ml_engine.query(req.query, source_id=source_id, is_stream=is_live)
        
        # Audit successful queries in the local SQL database
        if result.get("status") != "error":
            history_log = models.QueryHistoryDB(
                user_query=req.query, 
                ai_response=result.get("response", "Match found."),
                frame_path=result.get("frame_path", ""), 
                video_source_id=result.get("source_id", "unknown")
            )
            db.add(history_log)
            db.commit()
            
        return result
    except Exception as e:
        return {"status": "error", "message": "Query crashed.", "developer_details": str(e)}


@router.post("/trace")
async def detective_trace(req: QueryRequest, db: Session = Depends(get_db)):
    """
    Detective Mode: Traces a target's chronological trajectory across all cameras.
    """
    print(f"[Query Router] POST /api/trace - Trace initiated for target: '{req.query}'")
    
    # 🛡️ --- ArmorIQ Privacy Guardrail Intercept ---
    armoriq_result = armoriq_supervisor.evaluate_request(req.query, context="global")
    if armoriq_result["status"] == "blocked":
        return armoriq_result
    # ----------------------------------------------
    
    if not state.ml_engine:
        return {"status": "error", "message": "ML Engine not loaded. Cannot perform trace."}
        
    try:
        # Pass trajectory building tasks to the modular ML pipeline
        result = state.ml_engine.track_timeline(req.query)
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": "The Detective Engine failed. Check ML console logs.",
            "developer_details": str(e)
        }


@router.post("/search-image")
async def visual_suspect_search(
    file: UploadFile = File(...), 
    query: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Visual Search: Upload a mugshot to locate a suspect in ingested footage.
    Fuses the visual vector from the image with any contextual text tags.
    """
    print(f"[Query Router] POST /api/search-image - Mugshot: '{file.filename}' Context: '{query or 'None'}'")
    
    # 🛡️ --- ArmorIQ Privacy Guardrail Intercept ---
    if query:
        armoriq_result = armoriq_supervisor.evaluate_request(query, context="global")
        if armoriq_result["status"] == "blocked":
            return armoriq_result
    # ----------------------------------------------
    
    if not state.ml_engine:
        return {"status": "error", "message": "ML Engine not loaded. Cannot perform visual search."}
        
    try:
        # Create directory to store visual target uploads
        temp_dir = "./data/suspect_uploads/"
        os.makedirs(temp_dir, exist_ok=True)
        img_path = os.path.join(temp_dir, file.filename)
        
        # Save photo file to disk
        with open(img_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Execute the reverse-image search visual pipeline
        result = state.ml_engine.find_suspect_by_image(img_path, text_query=query)
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": "Visual search failed. Check if uploaded file is a valid image.",
            "developer_details": str(e)
        }
