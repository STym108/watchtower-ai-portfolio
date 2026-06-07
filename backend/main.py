"""
backend/main.py — FastAPI Main Server Orchestrator
===================================================
This file serves as the main entry point for the WatchTower.ai backend.
It initializes the FastAPI app instance, configures CORS middleware, mounts
local storage directories for static file asset serving, and registers all 
route routers (auth, media, queries, alerts).

It also starts the background threat audit daemon inside the async event loop 
on server startup.

Coordination:
- Boots the backend server (e.g. uvicorn backend.main:app).
- Coordinates with: backend/state.py, backend/routes/*.py
"""

import os
import sys
import time
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Insert root path to sys.path so we can import project modules cleanly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.models as models
from backend.database import engine, SessionLocal
import backend.state as state

# Import modular router groups
from backend.routes import auth, media, queries, alerts

# 1. Initialize DB tables (creates SQLite database models automatically)
models.Base.metadata.create_all(bind=engine)

# 2. Initialize FastAPI app
app = FastAPI(
    title="WatchTower.ai Backend",
    description="Surveillance Intelligence & Cross-Camera Lineage Tracking API"
)

# 3. Configure CORS middleware (cross-origin access for frontend development server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Create local folder directories for media storage
os.makedirs("data", exist_ok=True)
os.makedirs("data/frames", exist_ok=True)
os.makedirs("data/videos", exist_ok=True)
os.makedirs("data/vector_db", exist_ok=True)

# 5. Mount static directories so uploaded media and frame captures are viewable over HTTP
app.mount("/data", StaticFiles(directory="data"), name="data")

# 6. Register modular routers
app.include_router(auth.router)
app.include_router(media.router)
app.include_router(queries.router)
app.include_router(alerts.router)


# ──────────────────────────────────────────────────────────────────────────
# 7. Threat Auditor Background Daemon Loop
# ──────────────────────────────────────────────────────────────────────────

async def background_alert_daemon():
    """
    Continuous background daemon running concurrently in the server's event loop.
    Iterates over active operator rules, queries live cameras, handles suspect transitions,
    and logs threat reports to the SQLite DB and broadcasts them over websockets.
    """
    print("🚁 [Threat Daemon] Active and monitoring surveillance grid.")
    while True:
        db = SessionLocal()
        try:
            active_rules_count = db.query(models.AlertRuleDB).filter(models.AlertRuleDB.is_active == True).count()
            if active_rules_count == 0:
                db.close()
                await asyncio.sleep(5)
                continue

            active_rules = db.query(models.AlertRuleDB).filter(models.AlertRuleDB.is_active == True).all()
            for rule_db in active_rules:
                rule_text = rule_db.condition
                
                if state.ml_engine:
                    try:
                        # Restrict the camera live search range to the last 30 seconds
                        search_bound = time.time() - 30.0
                        result = state.ml_engine.query(
                            text_query=rule_text, 
                            is_stream=True, 
                            min_timestamp=search_bound
                        )
                        
                        if result.get("status") != "error":
                            ai_response = result.get("response", "").lower()
                            
                            # Check if the model confirms the presence of the anomaly
                            if "yes" in ai_response or "match found" in ai_response:
                                current_cam = result.get("source_id")
                                last_seen_cam = state.global_suspect_tracker.get(rule_text)
                                
                                # [BUG FIX] 1. Audit log triggered threat in SQL database
                                new_log = models.TriggeredAlertDB(
                                    rule_tested=rule_text,
                                    ai_analysis=result.get("response", "Match found."),
                                    timestamp_seconds=result.get("clip_start", 0),
                                    video_source_id=result.get("source_id", "unknown")
                                )
                                db.add(new_log)
                                db.commit()

                                # [BUG FIX] 2. Push alert to all connected dashboard websockets
                                await state.notifier.broadcast({
                                    "type": "NEW_ALERT",
                                    "rule": rule_text,
                                    "ai_analysis": new_log.ai_analysis,
                                    "timestamp": new_log.timestamp_seconds,
                                    "frame_path": result.get("frame_path")
                                })
                                
                                # === STATE 1: INITIAL DISCOVERY ===
                                if last_seen_cam is None:
                                    print(f"🚨 [Threat Alert] NEW TARGET DETECTED: '{rule_text}' @ Sector [{current_cam}]")
                                    state.global_suspect_tracker[rule_text] = current_cam
                                    
                                    # Send Telegram notification
                                    alert_text = (
                                        f"🚁 OVERWATCH DETECTED THREAT 🚨\n"
                                        f"Identifier: {rule_text}\n"
                                        f"Sector Matrix: Location [{current_cam}]\n\n"
                                        f"AI Notes: {result.get('response', 'Matched.')}"
                                    )
                                    state.send_telegram_alert(alert_text, result.get("frame_path"))
                                    
                                    # Play Voice Alarm
                                    state.speak_alarm(f"Intruder Alert. Security breach at {current_cam}!")
                                
                                # === STATE 2: TARGET TRANSITIONING BETWEEN CAMERAS ===
                                elif current_cam != last_seen_cam:
                                    print(f"🚁 [Threat Alert] TARGET TRANSITION: '{rule_text}' from Sector [{last_seen_cam}] → Sector [{current_cam}]")
                                    
                                    # Send Telegram transition notification
                                    alert_text = (
                                        f"🚁 OVERWATCH EVENT: Suspect Transition Matrix Detected 🚨\n"
                                        f"Target Identifier: {rule_text}\n"
                                        f"Sector Matrix transition: From [{last_seen_cam}] into [{current_cam}]"
                                    )
                                    state.send_telegram_alert(alert_text, result.get("frame_path"))
                                    
                                    state.global_suspect_tracker[rule_text] = current_cam
                                    
                                    # Play Voice Alarm
                                    state.speak_alarm(f"Update. Target shifted from {last_seen_cam} to {current_cam}!")
                                
                    except Exception as e:
                         print(f"🛑 [Threat Daemon] Monitor cycle execution failed: {e}")
        finally:
            db.close()
            
        await asyncio.sleep(10)  # Check threat rules every 10 seconds


@app.on_event("startup")
async def startup_event():
    """FastAPI startup handler. Captures running loop and spawns the background threat daemon task."""
    state.main_loop = asyncio.get_running_loop()
    asyncio.create_task(background_alert_daemon())
