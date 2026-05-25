import os
import dotenv
import hashlib
from google import genai

# Load Environment from root
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
dotenv.load_dotenv(env_path, override=True)

class SecurityGuardrailSupervisor:
    def __init__(self):
        # 🧠 Policy Engine (Gemini 2.5 Flash)
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            self.vlm_client = genai.Client(api_key=gemini_key)
            self.model_name = "gemini-2.5-flash"
            self.config = {"temperature": 0.0} # Deterministic policy enforcement
            print("🛡️ [Security Guardrails] Custom Policy Engine Initialized successfully.")
        else:
            self.vlm_client = None
            print("⚠️ [Security Guardrails] Warning: GEMINI_API_KEY not found. Running in local keyword mode.")

    def evaluate_request(self, query: str, context: str = "global") -> dict:
        """
        Custom Security & Privacy Policy Interceptor.
        Implements a two-layer security validation loop:
        1. Local Rule-Based Keyword Filtering (Demographics, Harassment, Privacy Zones)
        2. Gemini-Based LLM Intent Analysis (Detects visual profiling vs safety threats)
        """
        print(f"🛡️ [Security Guardrails] Evaluating operator search: '{query}' ({context})")
        logic_query = query.lower()

        # --- LAYER 1: Rule-Based Local Hard Blocks ---
        # Immediate local blocks for protected/private parameters
        hard_blocks = {
            "demographics": ["religion", "race", "ethnic", "caste", "nationality", "muslim", "hindu", "christian", "black", "white"],
            "gender/ethics": ["girl", "woman", "bikini", "dress", "shorts", "sexy", "beautiful", "hottie", "men", "boy", "naked", "nude"],
            "privacy": ["zoom", "face", "closer", "identifier", "follow"]
        }
        
        for category, keywords in hard_blocks.items():
            if any(word in logic_query for word in keywords):
                print(f"🚫 [Security Guardrails] BLOCK (Local Category Detected): '{category}' query.")
                return {
                    "status": "blocked", 
                    "message": f"Security Guardrail: Query contains restricted descriptive attributes ({category}) which are prohibited under local privacy guidelines."
                }

        # Privacy Zone Ingress Check
        restricted_zones = ["bathroom", "restroom", "locker", "private"]
        if context and any(zone in context.lower() for zone in restricted_zones):
             if not any(k in logic_query for k in ["weapon", "gun", "knife", "threat"]):
                 return {
                     "status": "blocked", 
                     "message": "Security Guardrail: Direct tracking is prohibited inside restricted privacy zones."
                 }

        # --- LAYER 2: LLM-Based Operator Intent Validation ---
        if not self.vlm_client:
             # Local fallback (allow if it passed Layer 1 keywords)
             return {"status": "allowed", "note": "Local verification fallback"}

        prompt = f"""
        You are the Intent Sentry for a CCTV Security SaaS. 
        Evaluate the human operator's search intent: "{query}"

        STRICT BOUNDARIES:
        - BLOCKED: Demographic profiling or tracking specific people by clothes/gender alone.
        - BLOCKED: Identifying children or harassment.
        - AUTHORIZED: Tracking Crimes, Weapons, or generic Narrative descriptions (e.g. "what is happening", "finding tools").

        Task: Return only 'ALLOWED' or 'BLOCKED' on line 1, followed by a brief reason.
        """

        try:
            assessment = self.vlm_client.models.generate_content(
                model=self.model_name, contents=[prompt], config=self.config
            )
            lines = [l.strip() for l in assessment.text.strip().split('\n') if l.strip()]
            decision = lines[0].upper()
            reason = lines[1] if len(lines) > 1 else "Matches acceptable security parameters."

            if "BLOCKED" in decision:
                print(f"🚫 [Security Guardrails] BLOCK (LLM Intent Blocked): {reason}")
                return {"status": "blocked", "message": f"Security Guardrail: {reason}"}

            # Generate a secure execution token locally using md5 hash of query
            token_seed = f"watchtower_secure_auth_{query}_{context}"
            auth_token = f"TOKEN_{hashlib.md5(token_seed.encode()).hexdigest()[:8].upper()}"

            print(f"✅ [Security Guardrails] Intent Authorized successfully: {auth_token}")
            return {
                "status": "allowed", 
                "armor_token": auth_token,  # Keep parameter name for backend compatibility
                "reason": reason
            }

        except Exception as e:
            print(f"⚠️ [Security Guardrails] LLM Validation Failed: {e}")
            # If API is down, fallback to allowing if Layer 1 check succeeded
            return {"status": "allowed", "note": "Local fallback check only."}

# Keep the singleton name compatible with the backend main.py
armoriq_supervisor = SecurityGuardrailSupervisor()
