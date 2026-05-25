from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Depends, HTTPException, Cookie, Response, WebSocket, WebSocketDisconnect, Header, Form
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
import sys
import asyncio
import requests
import threading
import cv2 
import time
from sqlalchemy.orm import Session
from typing import Optional, List
import dotenv

# Import authentication utilities
from backend.auth import (
    hash_password, 
    verify_password, 
    create_tokens,
    verify_token,
    get_user_id_from_token,
    UserResponse,
    TokenResponse,
    TokenRequest
)
from backend.superplane_client import superplane
# =====================================================================
# 1. SETUP & ALIGNMENT WITH ML TEAMMATE
# =====================================================================

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.pipelineY import OfflineVideoPipeline
from backend.armoriq import armoriq_supervisor

# =====================================================================
# WEBSOCKET MANAGER
# =====================================================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Failed to send to a websocket client: {e}")

notifier = ConnectionManager()

os.makedirs("data", exist_ok=True)
os.makedirs("data/frames", exist_ok=True)
os.makedirs("data/videos", exist_ok=True)
os.makedirs("data/vector_db", exist_ok=True)

app = FastAPI(title="WatchTower.ai Backend")

app.mount("/data", StaticFiles(directory="data"), name="data")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(os.path.dirname(base_dir), ".env")
dotenv.load_dotenv(env_path, override=True)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ CRITICAL ERROR: GEMINI_API_KEY could not be loaded!")
else:
    print(f"✅ [Backend] GEMINI_API_KEY loaded successfully. (Ends with: ...{api_key[-4:]})")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_alert(text: str, image_path: str = None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as image_file:
                res = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                    data={"chat_id": TELEGRAM_CHAT_ID, "caption": text},
                    files={"photo": image_file}
                )
            print(f"📡 [Telegram API] Photo Status: {res.status_code} | Resp: {res.text}")
        else:
            res = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": text}
            )
            print(f"📡 [Telegram API] Message Status: {res.status_code} | Resp: {res.text}")
    except Exception as e:
        print(f"❌ Failed to send Telegram alert: {e}")
    else:
        print(f"✅ Telegram alert sent successfully to {TELEGRAM_CHAT_ID}")

if OfflineVideoPipeline:
    ml_engine = OfflineVideoPipeline(api_key=api_key, collection_name="cctv_main_stream")
else:
    ml_engine = None

# =====================================================================
# 2. REAL SQLITE DATABASE SETUP
# =====================================================================
from backend.database import engine, SessionLocal
import backend.models as models

models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request_authorization: Optional[str] = Header(None, alias="Authorization"), db: Session = Depends(get_db)) -> models.User:
#def get_current_user(request_authorization: Optional[str] = None, db: Session = Depends(get_db)) -> models.User:
    token = None
    if request_authorization and request_authorization.startswith("Bearer "):
        token = request_authorization[7:]
    
    if not token:
        raise HTTPException(status_code=401, detail="No valid token provided. Have you logged in?")
    
    try:
        payload = verify_token(token)
        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        
        if user_id is None or email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# =====================================================================
# SHARED STATE (Moved from Multiprocessing to standard Memory for Threads)
# =====================================================================
latest_frames = {}
stream_orientations = {}
active_stream_info = {}
video_processing_status = {}

class TrackedValue:
    def __init__(self, v): self.value = v
last_active_source = TrackedValue("")

rule_last_triggered = {} 
new_frame_events = {} 
main_loop = None # Will store the asyncio event loop

# =====================================================================
# 3. DATA MODELS
# =====================================================================
class UserLogin(BaseModel): email: str; password: str
class UserSignup(BaseModel):
    email: str; password: str; full_name: str = None; phone: str = None
    telegram_handle: str = None; profile_picture: str = None
class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None; phone: Optional[str] = None
    telegram_handle: Optional[str] = None; profile_picture: Optional[str] = None
class AlertRule(BaseModel): condition: str
class StreamConfig(BaseModel): stream_url: str; source_name: str = "cam_1"
class LivestreamRequest(BaseModel): streams: List[StreamConfig]
class QueryRequest(BaseModel): query: str
class SpeakRequest(BaseModel):
    text: str

# =====================================================================
# 4. API ENDPOINTS - AUTHENTICATION
# =====================================================================
@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await notifier.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text() 
    except WebSocketDisconnect:
        notifier.disconnect(websocket)

@app.post("/api/auth/signup", response_model=TokenResponse)
async def signup(user: UserSignup, db: Session = Depends(get_db)):
    print(f"[API] POST /api/auth/signup - Attempting signup for email: {user.email}")
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user: 
        print(f"[API] POST /api/auth/signup - Failed: Email {user.email} already registered.")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = hash_password(user.password)
    db_user = models.User(
        email=user.email, hashed_password=hashed_password, full_name=user.full_name,
        phone=user.phone, telegram_handle=user.telegram_handle, profile_picture=user.profile_picture, is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return create_tokens(db_user.id, db_user.email)

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(user: UserLogin, response: Response, db: Session = Depends(get_db)):
    print(f"[API] POST /api/auth/login - Attempting login for email: {user.email}")
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not db_user.is_active or not verify_password(user.password, db_user.hashed_password):
        print(f"[API] POST /api/auth/login - Failed for email: {user.email}")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    tokens = create_tokens(db_user.id, db_user.email)
    response.set_cookie(key="access_token", value=tokens.access_token, httponly=True, samesite="lax", max_age=86400)
    response.set_cookie(key="refresh_token", value=tokens.refresh_token, httponly=True, samesite="lax", max_age=604800)
    return tokens

@app.get("/api/auth/profile", response_model=UserResponse)
async def get_profile(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    print(f"[API] GET /api/auth/profile - Fetching current user profile")
    current_user = get_current_user(request_authorization=authorization, db=db)
    return current_user

@app.put("/api/auth/profile", response_model=UserResponse)
async def update_profile(profile_update: UserProfileUpdate, authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    current_user = get_current_user(request_authorization=authorization, db=db)
    if profile_update.full_name is not None: current_user.full_name = profile_update.full_name
    if profile_update.phone is not None: current_user.phone = profile_update.phone
    if profile_update.telegram_handle is not None: current_user.telegram_handle = profile_update.telegram_handle
    if profile_update.profile_picture is not None: current_user.profile_picture = profile_update.profile_picture
    db.commit()
    db.refresh(current_user)
    return current_user

@app.post("/api/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return JSONResponse(status_code=200, content={"status": "success", "message": "Logged out successfully"})

@app.post("/api/auth/refresh", response_model=TokenResponse)
async def refresh_token(req: TokenRequest, db: Session = Depends(get_db)):
    try:
        payload = verify_token(req.refresh_token)
        user = db.query(models.User).filter(models.User.id == payload.get("user_id")).first()
        if not user or not user.is_active: raise HTTPException(status_code=401, detail="User not found")
        return create_tokens(user.id, user.email)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {str(e)}")

@app.get("/api/auth/verify")
async def verify_auth(authorization: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        user = get_current_user(request_authorization=authorization, db=db)
        return {"status": "valid", "user_id": user.id, "email": user.email, "full_name": user.full_name}
    except HTTPException as e:
        return {"status": "invalid", "detail": e.detail}


# =====================================================================
# 5. API ENDPOINTS - MEDIA & ALERTS
# =====================================================================
@app.get("/api/media/status")
async def check_processing_status():
    print(f"[API] GET /api/media/status - Current raw status dictionary in memory: {video_processing_status}")
    if not video_processing_status: return {"status": "idle", "raw_status": {}}
    statuses = list(video_processing_status.values())
    if "processing" in statuses: return {"status": "processing", "raw_status": video_processing_status}
    elif "completed" in statuses: return {"status": "completed", "raw_status": video_processing_status}
    for s in statuses:
        if isinstance(s, str) and s.startswith("error"): return {"status": "failed", "raw_status": video_processing_status}
    return {"status": "idle", "raw_status": video_processing_status}

def process_video_task(file_path: str, source_id: str, status_dict, frame_dict, orientation_dict, collection_name="cctv_main_stream"):
    """ Threaded background task to safely process video without crashing PyTorch """
    print(f"🎯 [Thread] Entered process_video_task for {source_id}")
    status_dict[source_id] = "processing"
    
    def frame_update_callback(frame):
        if frame is None: return
        try:
            h, w = frame.shape[:2]
            orientation_dict[source_id] = "portrait" if h > w else "landscape"
            
            _, buffer = cv2.imencode('.jpg', frame)
            frame_dict[source_id] = buffer.tobytes()
            
            # TRIGGER EVENT SAFELY for Asyncio
            if source_id in new_frame_events:
                event = new_frame_events[source_id]
                global main_loop
                if main_loop and not main_loop.is_closed():
                    main_loop.call_soon_threadsafe(event.set)
        except Exception as e:
            print(f"FAILED to update frame for {source_id}: {e}")

    active_stream_info[source_id] = file_path 
    
    try:
        if ml_engine:
            print(f"✅ [Thread] ML Engine is PRESENT. Starting ingestion...")
            ml_engine.ingest_video(file_path, source_id, collection_name=collection_name, on_frame=frame_update_callback)
        else:
             print(f"❌ [Thread] CRITICAL: ML Engine is MISSING!")
             
        status_dict[source_id] = "completed"
        print(f"🏁 [Thread] Task COMPLETED for {source_id}")
        
        # Only delete local uploads upon complete SUCCESS!
        if not file_path.startswith("http") and os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        status_dict[source_id] = f"error: {str(e)}"
        print(f"❌ [Thread] Processing CRASHED for {source_id}: {e}")

@app.post("/api/media/livestream")
async def start_livestream(req: LivestreamRequest):
    print(f"[API] POST /api/media/livestream - Incoming request to start streams: {[config.source_name for config in req.streams]}")
    active_streams = req.streams[:3] 

    
    for config in active_streams:
         print(f"🚀 LAUNCHING Thread for {config.source_name} (Collection: live_cctv_stream)")
         thread = threading.Thread(
             target=process_video_task, 
             args=(config.stream_url, config.source_name, video_processing_status, latest_frames, stream_orientations, "live_cctv_stream"),
             daemon=True
         )
         thread.start()
         
    if active_streams:
        last_active_source.value = active_streams[-1].source_name
         
    return {"status": "success", "message": f"Successfully tracing {len(active_streams)} camera streams!"}

@app.get("/api/media/stream/{source_id}")
async def get_video_stream(source_id: str):
    if source_id not in new_frame_events:
        new_frame_events[source_id] = asyncio.Event()
    
    event = new_frame_events[source_id]

    async def frame_generator():
        while True:
            await event.wait()
            event.clear()
            
            frame_bytes = latest_frames.get(source_id)
            if frame_bytes:
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/media/orientation/{source_id}")
async def get_stream_orientation(source_id: str):
    return {"orientation": stream_orientations.get(source_id, "landscape")}

@app.post("/api/media/upload")
async def upload_video(file: UploadFile = File(...)):
    print(f"[API] POST /api/media/upload - Receiving file upload: {file.filename}")
    base_dir = os.path.abspath(os.curdir)
    save_dir = os.path.join(base_dir, "data", "videos")
    os.makedirs(save_dir, exist_ok=True)
    
    safe_filename = os.path.basename(file.filename)
    file_path = os.path.join(save_dir, safe_filename)
    print(f"📥 [Upload] Saving video to ABSOLUTE PATH: {file_path}")
    
    # FIX: Write file chunks safely so memory doesn't blow up and file isn't 0 bytes!
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024): # 1MB chunks
            buffer.write(chunk)
            
    if os.path.getsize(file_path) == 0:
        return {"status": "error", "message": "Failed to save file. File is empty."}
        
    print(f"✅ [Upload] File successfully saved. Size: {os.path.getsize(file_path)} bytes")
        
    video_title = os.path.splitext(safe_filename)[0]
    last_active_source.value = video_title
    video_processing_status[video_title] = "processing"

    print(f"🚀 LAUNCHING upload Thread for {video_title} (Collection: uploaded_vault)")
    thread = threading.Thread(
        target=process_video_task, 
        args=(file_path, video_title, video_processing_status, latest_frames, stream_orientations, "uploaded_vault"),
        daemon=True
    )
    thread.start()
        
    return {"status": "processing", "message": f"Video successfully saved. Processing started."}

@app.post("/api/query")
async def manual_query(req: QueryRequest, db: Session = Depends(get_db)):
    print(f"[API] POST /api/query - User requested search: '{req.query}'")
    if not ml_engine: 
        print("[API] POST /api/query - Warning: ML Engine not loaded.")
        return {"response": "Warning: ML Engine not loaded."}
        
    try:
        source_id = last_active_source.value
        if not source_id:
             return {"status": "error", "message": "No active video or stream found."}
             
        # --- ArmorIQ Intercept ---
        armoriq_result = armoriq_supervisor.evaluate_request(req.query, context=source_id)
        if armoriq_result["status"] == "blocked":
            return armoriq_result
        # -------------------------
             
        is_live = source_id in active_stream_info and active_stream_info[source_id].startswith("http")
        print(f"🕵️ [Manual Query] Searching '{req.query}' in {'LIVE' if is_live else 'UPLOADS'} (Source: {source_id})")
        
        result = ml_engine.query(req.query, source_id=source_id, is_stream=is_live)
        
        if result.get("status") != "error":
            history_log = models.QueryHistoryDB(
                user_query=req.query, ai_response=result.get("response", "Match found."),
                frame_path=result.get("frame_path", ""), video_source_id=result.get("source_id", "unknown")
            )
            db.add(history_log)
            db.commit()
            
        return result
    except Exception as e:
        return {"status": "error", "message": "Crash occurred.", "developer_details": str(e)}

@app.post("/api/trace")
async def detective_trace(req: QueryRequest, db: Session = Depends(get_db)):
    """
    Detective Mode: Traces a suspect across all ingested cameras and builds a timeline report.
    This is for cross-camera lineage tracking.
    """
    print(f"[API] POST /api/trace - Detective trace initiated for: '{req.query}'")
    
    # --- ArmorIQ Intercept ---
    armoriq_result = armoriq_supervisor.evaluate_request(req.query, context="global")
    if armoriq_result["status"] == "blocked":
        return armoriq_result
    # -------------------------
    
    if not ml_engine:
        return {"status": "error", "message": "ML Engine not loaded. Cannot perform trace."}
        
    try:
        source_id = last_active_source.value
        # Pass the query to the Detective Trace engine
        result = ml_engine.track_timeline(req.query)
        
        # We can also save this to history if needed, but for now we'll just return it
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": "The Detective Engine failed. Check your ML logs.",
            "developer_details": str(e)
        }


@app.post("/api/search-image")
async def visual_suspect_search(
    file: UploadFile = File(...), 
    query: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Mugshot Search: Upload a photo of a suspect to find them in the footage!
    Now supports situational context (e.g. 'Find this person holding a laptop').
    """
    print(f"[API] POST /api/search-image - Searching image '{file.filename}' with context: '{query}'")
    
    # --- ArmorIQ Intercept ---
    if query:
        armoriq_result = armoriq_supervisor.evaluate_request(query, context="global")
        if armoriq_result["status"] == "blocked":
            return armoriq_result
    # -------------------------
    
    if not ml_engine:
        return {"status": "error", "message": "ML Engine not loaded. Cannot perform visual search."}
        
    try:
        # 📂 Create a temp folder for uploaded suspect photos
        temp_dir = "./data/suspect_uploads/"
        os.makedirs(temp_dir, exist_ok=True)
        img_path = os.path.join(temp_dir, file.filename)
        
        # 💾 Save the suspect's photo to disk
        with open(img_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 🕵️ Call the ML "Reverse Image" Kernel (Now with text fusion!)
        source_id = last_active_source.value
        result = ml_engine.find_suspect_by_image(img_path, text_query=query)
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": "Visual search failed. Is the uploaded file a valid image?",
            "developer_details": str(e)
        }


@app.post("/api/speak")
async def manual_speak(req: SpeakRequest):
    """
    On-Demand Voice: Frontend triggers the server to speak an AI report.
    This uses the 'clean_text_for_speech' filter to strip Markdown (**, ###).
    """
    try:
        speak_alarm(req.text)
        return {"status": "success", "message": "Voice triggered successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/alerts/setup")
async def setup_alert(rule: AlertRule, db: Session = Depends(get_db)):
    print(f"[API] POST /api/alerts/setup - Adding new alert condition: '{rule.condition}'")
    
    # --- ArmorIQ Intercept ---
    armoriq_result = armoriq_supervisor.evaluate_request(rule.condition, context="global")
    if armoriq_result["status"] == "blocked":
        return armoriq_result
    # -------------------------
    
    db_rule = models.AlertRuleDB(condition=rule.condition)
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return {"status": "success", "message": f"Alert rule activated permanently: '{rule.condition}'"}

@app.get("/api/alerts/active")
async def get_active_alerts(db: Session = Depends(get_db)):
    active_rules = db.query(models.AlertRuleDB).filter(models.AlertRuleDB.is_active == True).all()
    return {"status": "success", "rules": active_rules}

@app.delete("/api/alerts/{rule_id}")
async def delete_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(models.AlertRuleDB).filter(models.AlertRuleDB.id == rule_id).first()
    if not rule: raise HTTPException(status_code=404, detail="Alert rule not found")
    rule.is_active = False
    db.commit()
    return {"status": "success", "message": "Alert rule deactivated successfully."}

@app.get("/api/alerts/logs")
async def get_alert_logs(db: Session = Depends(get_db)):
    logs = db.query(models.TriggeredAlertDB).order_by(models.TriggeredAlertDB.id.desc()).all()
    return {"total_alerts": len(logs), "logs": logs}

@app.delete("/api/alerts/logs/purge")
async def purge_alert_logs(db: Session = Depends(get_db)):
    try:
        db.query(models.TriggeredAlertDB).delete()
        db.commit()
        return {"status": "success", "message": "All alert logs cleared from database."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to purge logs: {str(e)}")

@app.get("/api/query/history")
async def get_query_history(db: Session = Depends(get_db)):
    history = db.query(models.QueryHistoryDB).order_by(models.QueryHistoryDB.created_at.desc()).all()
    return {"total_queries": len(history), "history": history}

# =====================================================================
# 5. THE BACKGROUND DAEMON LOOP
# =====================================================================

async def background_alert_daemon():
    while True:
        db = SessionLocal()
        try:
            active_rules_count = db.query(models.AlertRuleDB).filter(models.AlertRuleDB.is_active == True).count()
            if active_rules_count == 0:
                db.close(); await asyncio.sleep(5); continue

            active_rules = db.query(models.AlertRuleDB).filter(models.AlertRuleDB.is_active == True).all()
            for rule_db in active_rules:
                rule_text = rule_db.condition
                
                if ml_engine:
                    try:
                        search_bound = time.time() - 30.0
                        result = ml_engine.query(rule_text, is_stream=True, min_timestamp=search_bound)
                        
                        if result.get("status") != "error":
                            ai_response = result.get("response", "").lower()
                            
                            if "yes" in ai_response or "match found" in ai_response:
                                current_cam = result.get("source_id")
                                last_seen_cam = global_suspect_tracker.get(rule_text)
                                
                                # === STATE 1: INITIAL DISCOVERY ===
                                if last_seen_cam is None:
                                    print(f"🚨 [NEW THREAT DETECTED] -> {rule_text} @ {current_cam}")
                                    global_suspect_tracker[rule_text] = current_cam
                                    
                                    # Alert SuperPlane to spin up Jira/Incidents
                                    superplane.alert_anomaly_spotted(
                                        rule_condition=rule_text, source_camera=current_cam,
                                        ai_analysis=result.get("response", "Matched."),
                                        image_url=result.get("frame_path")
                                    )
                                    
                                    os.system(f'say "Intruder Alert. Security breach at {current_cam}!" &')
                                
                                # === STATE 2: TARGET MOVING ACROSS CAMERAS ===
                                elif current_cam != last_seen_cam:
                                    print(f"🚁 [LIVE OVERWATCH] Target {rule_text} transitioned: {last_seen_cam} -> {current_cam}")
                                    
                                    # Tell SuperPlane to ping Telegram with the location change
                                    superplane.alert_suspect_tracking(
                                        suspect_profile=rule_text, 
                                        new_camera_id=current_cam, 
                                        old_camera_id=last_seen_cam
                                    )
                                    
                                    global_suspect_tracker[rule_text] = current_cam
                                    os.system(f'say "Update. Target shifted from {last_seen_cam} to {current_cam}!" &')
                                
                                # WE DO NOT DEACTIVATE THE RULE (rule_db.is_active = False)
                                # Keep it True so we track the attacker infinitely across the facility!
                    except Exception as e:
                         print(f"🛑 [Daemon] Skynet override failed: {e}")
        finally:
            db.close()
            
        await asyncio.sleep(10) # Polling hyper-fast every 5s for military-grade live tracking

"""
async def background_alert_daemon():
    while True:
        db = SessionLocal()
        try:
            active_rules_count = db.query(models.AlertRuleDB).filter(models.AlertRuleDB.is_active == True).count()
            is_any_stream_active = any(status == "processing" for status in video_processing_status.values())

            # DIAGNOSTIC LOG 1: Start of Cycle
            print(f"[Daemon DEBUG] Start Cycle - Active Rules: {active_rules_count} | Active Streams: {is_any_stream_active}")
            if not is_any_stream_active:
                 print(f"[Daemon DEBUG] No active streams found in: {video_processing_status}")

            if active_rules_count == 0 or not is_any_stream_active:
                db.close()
                await asyncio.sleep(10) 
                continue

            print(f"[Daemon] Waking up to check {active_rules_count} active alert rules against live feed...")
            active_rules = db.query(models.AlertRuleDB).filter(models.AlertRuleDB.is_active == True).all()
            
            for rule_db in active_rules:
                rule_text = rule_db.condition
                
                if ml_engine:
                    try:
                        print(f"[Daemon DEBUG] Querying AI for rule: {rule_text}")
                        result = ml_engine.query(rule_text, is_stream=True)
                        if result.get("status") != "error":
                            ai_response = result.get("response", "").lower()
                            print(f"[Daemon DEBUG] Raw AI Response for '{rule_text}': {ai_response}")
                            
                            
                            confirmation_words = ["yes","confirmed","verified","true"]
                            if any(f" {word} " in f" {ai_response} " for word in confirmation_words):
                                print(f"✅ [Daemon DEBUG] MATCH FOUND for rule: {rule_text}")
                                # now = time.time()
                                # last_fired = rule_last_triggered.get(rule_db.id, 0)
                                # if (now - last_fired) < 300: continue

                                new_log = models.TriggeredAlertDB(
                                    rule_tested=rule_text, ai_analysis=result.get("response", "Match found."),
                                    timestamp_seconds=result.get("clip_start", 0), video_source_id=result.get("source_id", "unknown")
                                )
                                db.add(new_log)
                                db.commit()
                                print(f"[Daemon DEBUG] Alert successfully saved to database.")
                                
                                send_telegram_alert(
                                    f"🚨 SECURITY ALERT 🚨\n\nRule: '{rule_text}'\n🔎 AI Notes: {new_log.ai_analysis}",
                                    result.get("frame_path")
                                )

                                
                                await notifier.broadcast({
                                    "type": "NEW_ALERT", "rule": rule_text,
                                    "ai_analysis": new_log.ai_analysis,
                                    "timestamp": new_log.timestamp_seconds, "frame_path": result.get("frame_path")
                                })
                                
                                safe_speech = rule_text.replace('"', '').replace("'", "")
                                phrase = f"Security Alert! Watch Tower detected {safe_speech} on the camera feed!"
                                
                                threading.Thread(target=speak_alarm, args=(phrase,), daemon=True).start()
                                rule_last_triggered[rule_db.id] = time.time()
                            else:
                                print(f"❌ [Daemon DEBUG] AI verified but said NO (or didn't use 'yes'/'match found')")
                        else:
                             print(f"⚠️ [Daemon DEBUG] ML Engine returned an error: {result.get('message')}")
                    except Exception as e:
                        if "429" in str(e) or "quota" in str(e).lower():
                            rule_db.is_active = False
                            db.commit()
                            print(f"🛑 [Daemon DEBUG] Quota exceeded. Deactivating rule: {rule_text}")
                        else:
                             print(f"🛑 [Daemon DEBUG] Exception during ML query: {e}")
        finally:
            db.close()
                
        # Wait 10 seconds before doing it all again (Reduced for faster demo)
        await asyncio.sleep(10)
"""



@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop() # Capture loop to trigger video frames cleanly!
    asyncio.create_task(background_alert_daemon())


def clean_text_for_speech(text: str) -> str:
    """
    Strips Markdown and special characters so the AI voice sounds human.
    Turns '**Match Found**' into 'Match Found'.
    """
    import re
    # Remove Bold/Italic asterisks
    text = text.replace("**", "").replace("*", "")
    # Remove Markdown headers (###)
    text = re.sub(r'#+\s*', '', text)
    # Remove bullet points at the start of lines
    text = re.sub(r'^\s*[-•+]\s*', '', text, flags=re.MULTILINE)
    # Clean up multiple newlines into single spaces for better flow
    text = text.replace("\n", " ").strip()
    return text

def speak_alarm(phrase: str):
    """
    Text-to-speech alarm using offline pyttsx3.
    Runs in a background thread to prevent UI freezing.
    """
    def _speak():
        try:
            # Clean the phrase before speaking
            clean_phrase = clean_text_for_speech(phrase)
            
            print("🤖 [Voice Engine] Using offline pyttsx3.")
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', 160) 
            engine.say(clean_phrase)
            engine.runAndWait()
            engine.stop()
            
        except Exception as e:
            print(f"❌ Voice Engine Critical Error: {e}")

    threading.Thread(target=_speak, daemon=True).start()

