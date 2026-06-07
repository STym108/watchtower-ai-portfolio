"""
backend/routes/alerts.py — Alerting, Auditing, and Websockets Router
===================================================================
Manages system tripwire rule definitions, logs auditing logs for triggered threat matches,
defines manual speech/audio alarm calls, and handles the WebSocket alert channel.

Coordination:
- Used by: backend/main.py (registered as router).
- Relies on: backend/state.py (for notifier ConnectionManager and speak_alarm tools).
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
import backend.models as models
import backend.state as state
from backend.armoriq import armoriq_supervisor

router = APIRouter(prefix="", tags=["Alerts & Auditing Operations"])


# ──────────────────────────────────────────────────────────────────────────
# 1. Pydantic Models
# ──────────────────────────────────────────────────────────────────────────

class AlertRule(BaseModel):
    condition: str

class SpeakRequest(BaseModel):
    text: str


# ──────────────────────────────────────────────────────────────────────────
# 2. WebSocket Alert Stream Handler
# ──────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket channel that accepts operator connections and registers them
    with state.notifier. Threat match events will be broadcasted to active sockets.
    """
    await state.notifier.connect(websocket)
    try:
        while True:
            # Keep the socket connection open to listen for client events
            await websocket.receive_text() 
    except WebSocketDisconnect:
        state.notifier.disconnect(websocket)


# ──────────────────────────────────────────────────────────────────────────
# 3. Alert & Audit Route Endpoints
# ──────────────────────────────────────────────────────────────────────────

@router.post("/api/alerts/setup")
async def setup_alert(rule: AlertRule, db: Session = Depends(get_db)):
    """
    Configures a new Tripwire active rule.
    Vets query parameters using ArmorIQ Guardrails prior to database insertion.
    """
    print(f"[Alert Router] Setup active rule condition: '{rule.condition}'")
    
    # 🛡️ --- ArmorIQ Privacy Guardrail Intercept ---
    armoriq_result = armoriq_supervisor.evaluate_request(rule.condition, context="global")
    if armoriq_result["status"] == "blocked":
        return armoriq_result
    # ----------------------------------------------
    
    db_rule = models.AlertRuleDB(condition=rule.condition)
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return {"status": "success", "message": f"Alert rule activated permanently: '{rule.condition}'"}


@router.get("/api/alerts/active")
async def get_active_alerts(db: Session = Depends(get_db)):
    """
    Retrieves all active Tripwire alert conditions currently monitored by the daemon.
    """
    active_rules = db.query(models.AlertRuleDB).filter(models.AlertRuleDB.is_active == True).all()
    return {"status": "success", "rules": active_rules}


@router.delete("/api/alerts/{rule_id}")
async def delete_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    """
    Deactivates (soft deletes) an alert tripwire rule by setting is_active = False.
    """
    rule = db.query(models.AlertRuleDB).filter(models.AlertRuleDB.id == rule_id).first()
    if not rule: 
        raise HTTPException(status_code=404, detail="Alert rule not found")
    rule.is_active = False
    db.commit()
    return {"status": "success", "message": "Alert rule deactivated successfully."}


@router.get("/api/alerts/logs")
async def get_alert_logs(db: Session = Depends(get_db)):
    """
    Retrieves history logs of all triggered AI alert conditions.
    """
    logs = db.query(models.TriggeredAlertDB).order_by(models.TriggeredAlertDB.id.desc()).all()
    return {"total_alerts": len(logs), "logs": logs}


@router.delete("/api/alerts/logs/purge")
async def purge_alert_logs(db: Session = Depends(get_db)):
    """
    Wipes triggered alert audit history logs from the database.
    """
    try:
        db.query(models.TriggeredAlertDB).delete()
        db.commit()
        return {"status": "success", "message": "All alert logs cleared from database."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to purge logs: {str(e)}")


@router.get("/api/query/history")
async def get_query_history(db: Session = Depends(get_db)):
    """
    Retrieves search logs history of manual queries executed by operators.
    """
    history = db.query(models.QueryHistoryDB).order_by(models.QueryHistoryDB.created_at.desc()).all()
    return {"total_queries": len(history), "history": history}


@router.post("/api/speak")
async def manual_speak(req: SpeakRequest):
    """
    Text-to-Speech manual override. Audibly speaks the provided text report.
    """
    try:
        state.speak_alarm(req.text)
        return {"status": "success", "message": "Voice triggered successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
