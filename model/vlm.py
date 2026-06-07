"""
model/vlm.py — Vision-Language Model (VLM) Manager
===================================================
This module manages downstream verification of video segments using the Gemini API.
Since vector search only finds visual similarities, we use a Vision-Language Model (VLM)
to perform deep context understanding (e.g. 'Is the suspect wearing a black shirt and holding a briefcase?').

Key Features:
- MD5-based query caching to avoid calling the Gemini API for duplicate queries (saves API quota).
- Smart image downscaling to reduce token cost and improve response latency.

Coordination:
- Used by: model/pipelineY.py (for processing multi-frame verification and timeline incident synthesis).
"""

import hashlib
from PIL import Image
from google import genai

class VLMManager:
    """
    Interfaces with the Google GenAI SDK (Gemini) to perform visual reasoning.
    """
    def __init__(self, api_key: str):
        # Initialize Google GenAI Client with the user's API key
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"
        
        # Simple in-memory cache to save API usage costs during development/demos
        self._cache: dict[str, str] = {}

    def resize_for_vlm(self, pil_img: Image.Image, max_side: int = 512) -> Image.Image:
        """
        Downsamples high-resolution frames before sending them to the Gemini API.
        
        Why we do this:
          Sending high-res 1080p or 4K frames consumes a massive number of API tokens,
          which eats up your Gemini quota rapidly. Resizing to a max-side of 512px
          retains enough detail for security analysis while reducing costs by up to 75%.
        """
        # Maintain aspect ratio while ensuring width and height do not exceed max_side
        pil_img.thumbnail((max_side, max_side), Image.LANCZOS)
        return pil_img

    def query(self, cache_key: str, contents: list) -> str:
        """
        Submits query instructions and images to the Gemini API.
        Uses MD5 caching to intercept identical queries.
        
        Parameters:
          - cache_key: Unique string containing query details (e.g., text search query or suspect image path).
          - contents: Mixed list containing the text prompt and PIL images to analyze.

        Returns:
          - String response from the Gemini model.
        """
        # Create a unique MD5 hash signature of the cache key
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
        
        if cache_hash in self._cache:
            print("👁️ [VLM Cache] Hit — serving cached Gemini response.")
            return self._cache[cache_hash]

        print(f"📡 [VLM API] Querying Gemini model '{self.model_name}'...")
        try:
            resp = self.client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            # Store successful response in the cache
            self._cache[cache_hash] = resp.text
            return resp.text
        except Exception as e:
            print(f"🛑 [VLM API] Error calling Gemini: {e}")
            return f"Error executing VLM verification: {e}"
