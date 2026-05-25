import os
import dotenv
from google import genai
from armoriq_sdk import ArmorIQClient

# Load Environment from root
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
dotenv.load_dotenv(env_path, override=True)

class ArmorIQGuard:
    def __init__(self):
        # 🛡️ Official ArmorIQ SDK Setup
        self.api_key = os.getenv("ARMORIQ_API_KEY")
        self.user_id = os.getenv("ARMORIQ_USER_ID", "hackathon-dev")
        self.agent_id = os.getenv("ARMORIQ_AGENT_ID", "watchtower-v1")
        
        # Initialize official ArmorIQ Client
        try:
            if self.api_key:
                self.client = ArmorIQClient(
                    api_key=self.api_key,
                    user_id=self.user_id,
                    agent_id=self.agent_id,
                    use_production=True # Ensure we use the live key from platform.armoriq.ai
                )
                print(f"🛡️ [ArmorIQ] SDK INITIALIZED. Agent: {self.agent_id}")
            else:
                self.client = None
                print("⚠️ [ArmorIQ] Warning: ARMORIQ_API_KEY not found. Running in simulation mode.")
        except Exception as e:
            print(f"❌ [ArmorIQ] SDK Initialization Error: {e}")
            self.client = None

        # 🧠 Policy Engine (Gemini 1.5 Flash)
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            self.vlm_client = genai.Client(api_key=gemini_key)
            self.model_name = "gemini-2.5-flash"
            self.config = {"temperature": 0.0} # Deterministic policy enforcement
        else:
            self.vlm_client = None

    def evaluate_request(self, query: str, context: str = "global") -> dict:
        """
        WatchTower Interceptor. 
        Implements: [Local Hard Block] -> [Capture Plan] -> [Intent Verification]
        """
        print(f"🛡️ [ArmorIQ] Intercepting Search: '{query}' ({context})")
        logic_query = query.lower()

        # --- 🛡️ LAYER 1: DETERMINISTIC LOCAL BLOCKS (Always First) ---
        # These are high-risk attributes that must be blocked regardless of AI decision.
        hard_blocks = {
            "demographics": ["religion", "race", "ethnic", "caste", "nationality", "muslim", "hindu", "christian", "black", "white"],
            "gender/ethics": ["girl", "woman", "bikini", "dress", "shorts", "sexy", "beautiful", "hottie", "men", "boy", "naked", "nude"],
            "privacy": ["zoom", "face", "closer", "identifier", "follow"]
        }
        
        for category, keywords in hard_blocks.items():
            if any(word in logic_query for word in keywords):
                print(f"🚫 [ArmorIQ] DETERMINISTIC BLOCK: '{category}' category detected in query.")
                return {
                    "status": "blocked", 
                    "message": f"ArmorIQ Guard: Query contains restricted descriptive attributes ({category}) which are prohibited under ethical guidelines."
                }

        # 1. Privacy Zone Check
        restricted_zones = ["bathroom", "restroom", "locker", "private"]
        if context and any(zone in context.lower() for zone in restricted_zones):
             if not any(k in logic_query for k in ["weapon", "gun", "knife", "threat"]):
                 return {
                     "status": "blocked", 
                     "message": "ArmorIQ: Direct surveillance is prohibited in Private Privacy Zones."
                 }

        # 2. AI INTENT ANALYSIS (The Intelligence Layer)
        if not self.vlm_client:
             return {"status": "allowed", "note": "Simulation mode"}

        prompt = f"""
        You are the Intent Sentry for to a CCTV Security SaaS. 
        Evaluate the human operator's intent: "{query}"

        STRICT BOUNDARIES:
        - BLOCKED: Demographic profiling or tracking specific people by clothes/gender alone.
        - BLOCKED: Identifying children or harassment.
        - AUTHORIZED: Tracking Crimes, Weapons, or generic Narrative descriptions (e.g. "what is happening").

        Task: Return only 'ALLOWED' or 'BLOCKED' on line 1, followed by a reason.
        """

        try:
            # Pre-flight check using Policy Engine
            assessment = self.vlm_client.models.generate_content(
                model=self.model_name, contents=[prompt], config=self.config
            )
            lines = [l.strip() for l in assessment.text.strip().split('\n') if l.strip()]
            decision = lines[0].upper()
            reason = lines[1] if len(lines) > 1 else "Protected by ethical guardrail."

            if "BLOCKED" in decision:
                return {"status": "blocked", "message": f"ArmorIQ Agent: {reason}"}

            # 3. OFFICIAL SDK CAPTURE (The Proof Layer)
            intent_token = "SIMULATED_TOKEN_VALID"
            if self.client:
                try:
                    plan = self.client.capture_plan(
                        llm="gemini-1.5-flash",
                        prompt=query,
                        plan={
                            "goal": f"Evaluate and execute safe query: {query}",
                            "steps": [
                                {
                                    "action": "execute_query",
                                    "mcp": "watchtower-mcp",
                                    "params": {"query": query, "context": context}
                                }
                            ]
                        }
                    )
                    intent_token = f"TOKEN_{plan.plan.get('hash', 'A1B2')[:8]}"
                except Exception as sdk_err:
                    print(f"⚠️ [ArmorIQ] SDK Note: {sdk_err}")

            print(f"✅ [ArmorIQ] Intent Authorized: {intent_token}")
            return {
                "status": "allowed", 
                "armor_token": intent_token,
                "reason": reason
            }

        except Exception as e:
            print(f"⚠️ [ArmorIQ] Cloud Check Failed: {e}")
            # If AI is down, we already passed the Layer 1 check above, 
            # so we allow for safety unless it's a known bad query.
            return {"status": "allowed", "note": "Local fallback check only."}

# Singleton instance
armoriq_supervisor = ArmorIQGuard()
