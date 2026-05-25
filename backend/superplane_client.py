import os
import requests
import time
from typing import Optional

SUPERPLANE_WEBHOOK_URL = os.getenv("SUPERPLANE_WEBHOOK_URL", "http://localhost:3000/api/webhook/watchtower")

class SuperPlaneOrchestrator:
    """
    Dedicated client for orchestrating Security SOAR operations through SuperPlane.
    Handles continuous suspect tracking workflows seamlessly bridging Python Edge and SuperPlane Logic Nodes.
    """
    
    def __init__(self, webhook_url: str = SUPERPLANE_WEBHOOK_URL):
        self.webhook_url = webhook_url

    def dispatch_event(self, event_type: str, priority: str, data: dict):
        """ The unified payload delivery vehicle routing intelligence directly into SuperPlane. """
        if not self.webhook_url or "localhost" in self.webhook_url and not os.getenv("SUPERPLANE_WEBHOOK_URL"):
            print("⚠️ [SuperPlane Client] Missing active webhook URL. Simulate logging event.")
            print(f"   ↳ {event_type} | Prio: {priority} | Data: {data}")
            return

        payload = {
            "id": f"evt_{int(time.time()*1000)}",
            "type": event_type, # e.g. "ANOMALY_DETECTED", "TARGET_RELOCATED"
            "priority": priority, # e.g. "CRITICAL", "ELEVATED"
            "timestamp": time.time(),
            "payload": data
        }

        try:
            # Drop timeout constraint so we don't hold the python lock during intense traffic
            res = requests.post(self.webhook_url, json=payload, timeout=2.5)
            if res.status_code in [200, 201, 202, 204]:
                print(f"🌐 [SuperPlane] Event '{event_type}' securely delivered to Event-Driven Workflow Canvas.")
            else:
                print(f"⚠️ [SuperPlane] Delivery failed with code {res.status_code}. Response: {res.text}")
        except Exception as e:
            print(f"❌ [SuperPlane] Delivery Exception: {str(e)}")


    def alert_anomaly_spotted(self, rule_condition: str, source_camera: str, ai_analysis: str, image_url: Optional[str] = None):
        """ 
        Triggered ONLY the very first time an anomaly (Tripwire) breaks the ML bounds.
        Kicks off SuperPlane Incident Creation flow.
        """
        self.dispatch_event(
            event_type="ANOMALY_DETECTED",
            priority="CRITICAL" if any(w in rule_condition.lower() for w in["gun", "weapon", "blood", "fire"]) else "HIGH",
            data={
                "trigger_rule": rule_condition,
                "current_location": source_camera,
                "raw_intel": ai_analysis,
                "evidence_url": image_url,
                "action_required": "Create Jira Ticket & Notify Shift Manager"
            }
        )

    def alert_suspect_tracking(self, suspect_profile: str, new_camera_id: str, old_camera_id: str):
        """
        Triggered repeatedly when the Engine determines a spatial jump across hardware nodes.
        SuperPlane intercepts this, queries the Trace API, and outputs live Telegram pathing.
        """
        self.dispatch_event(
            event_type="TARGET_RELOCATED",
            priority="CRITICAL",
            data={
                "suspect_profile": suspect_profile,
                "previous_node": old_camera_id,
                "current_node": new_camera_id,
                "action_required": "Pull updated Trace Matrix & Fire Telegram Field Update",
                # The callback pointer! Tells SuperPlane EXACTLY how to fetch the data payload natively
                "callback_trace_api": f"http://127.0.0.1:8000/api/trace",
                "query_param": suspect_profile
            }
        )
        
superplane = SuperPlaneOrchestrator()
