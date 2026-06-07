"""
pipeline.py — WatchTower.ai Unified ML Orchestration Engine
==========================================================
This file acts as the primary orchestrator for the WatchTower.ai machine learning engine.
It preserves the public API contract (the OfflineVideoPipeline class and all public method signatures)
to ensure compatibility with other backend layers.

Instead of containing all ML code in a single file, it delegates:
- Embedder (model/embedder.py): Handles hardware-accelerated CLIP embedding generation.
- VectorDBManager (model/vectordb.py): Handles ChromaDB persistence, storage, queries, and search filters.
- VLMManager (model/vlm.py): Handles Gemini API validation, cache control, frame downscaling, and prompt formatting.

Coordination:
- Used by: backend/main.py (for processing camera streams, user queries, timeline generation).
"""

import os
import shutil
import concurrent.futures
import cv2
from PIL import Image

# Import the decoupled modules
from model.embedder import Embedder, fuse_modalities
from model.vectordb import VectorDBManager
from model.vlm import VLMManager

# Allow OpenCV/FFmpeg to connect to IP cameras with self-signed HTTPS certs
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "tls_verify;0"


class OfflineVideoPipeline:
    """
    Unified Orchestrator implementing the public API of the ML engine.
    This class delegates details to the specialized sub-modules, making it highly readable.
    """

    # Router collections for video sources
    COLLECTION_LIVE     = "live_cctv_stream"
    COLLECTION_UPLOADED = "uploaded_vault"

    def __init__(self, api_key: str, collection_name: str = "cctv_main_stream"):
        """
        Initializes the sub-modules: Embedder, VectorDBManager, VLMManager,
        and setting up the async I/O worker thread pool.
        """
        # 1. Initialize core feature extraction (CLIP and PyTorch hardware selection)
        self.embedder = Embedder()
        self.device = self.embedder.device  # Expose property for status checking/diagnostics

        # 2. Initialize persistent Vector Database (ChromaDB client and collection storage)
        self.db = VectorDBManager(
            default_collection=collection_name,
            additional_collections=[self.COLLECTION_LIVE, self.COLLECTION_UPLOADED]
        )
        self.default_collection_name = collection_name

        # 3. Initialize Vision-Language Model (Gemini API with MD5 caching)
        self.vlm = VLMManager(api_key=api_key)

        # 4. Async I/O thread pool (saves JPEG frames to disk in the background to avoid write lag)
        self.io_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)

    # ──────────────────────────────────────────────────────────────────────────
    # Backward-Compatible Private Helper Methods
    # ──────────────────────────────────────────────────────────────────────────
    # These helpers redirect to the specific modules so that any internal
    # references in legacy backend imports or code remain intact.

    def _convert_cv2_to_hardware_tensor(self, frame_bgr):
        return self.embedder.convert_frame_to_tensor(frame_bgr)

    def _encode_image_tensor(self, tensor) -> "torch.Tensor":
        return self.embedder.encode_image_tensor(tensor)

    def _encode_text(self, text: str) -> "torch.Tensor":
        return self.embedder.encode_text(text)

    def _store_batch_hardware(self, tensor_list: list, metadatas: list, ids: list, collection_name: str):
        if not tensor_list:
            return
        features = self.embedder.encode_image_batch(tensor_list).cpu().tolist()
        self.db.add_embeddings(collection_name, features, metadatas, ids)

    def _vlm_query(self, cache_key: str, contents: list) -> str:
        return self.vlm.query(cache_key, contents)

    def _resize_for_vlm(self, pil_img: Image.Image, max_side: int = 512) -> Image.Image:
        return self.vlm.resize_for_vlm(pil_img, max_side)

    def _get_collection(self, collection_name: str):
        return self.db.get_collection(collection_name)

    # ──────────────────────────────────────────────────────────────────────────
    # Core Public API Methods
    # ──────────────────────────────────────────────────────────────────────────

    def ingest_video(self, video_path: str, source_id: str,
                     collection_name: str = None,
                     fps_to_extract: int = 1,
                     batch_size: int = 32,
                     on_frame=None):
        """
        Processes a video file, extracts frames, creates embeddings, and saves them to the DB.
        """
        if collection_name is None:
            collection_name = self.COLLECTION_UPLOADED

        # 1. Clear out previously saved frames
        frames_dir = f"./data/frames/{source_id}"
        if os.path.exists(frames_dir):
            shutil.rmtree(frames_dir)
        os.makedirs(frames_dir, exist_ok=True)

        # 2. Purge old vector database entries
        self.db.delete_source_data(collection_name, source_id)

        # 3. Read video file using OpenCV
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ [Ingestion] Could not open video: {video_path}")
            return

        fps            = round(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        frame_interval = max(1, int(fps / fps_to_extract))
        count          = 0

        print(f"📼 [Ingestion] Starting ingestion for '{video_path}' → [{collection_name}]")

        tensor_list, metadata_list, id_list = [], [], []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if on_frame:
                on_frame(frame)

            # Sample frames based on target extraction FPS
            if count % frame_interval == 0:
                timestamp  = count / fps
                frame_path = f"{frames_dir}/t_{timestamp:.1f}.jpg"
                metadata   = {
                    "source_id": source_id,
                    "timestamp": timestamp,
                    "frame_path": frame_path
                }

                # Save frame image as JPEG in background thread pool to prevent I/O blocking
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                self.io_pool.submit(pil_img.save, frame_path)

                # Preprocess OpenCV frame image on device
                hw_tensor = self.embedder.convert_frame_to_tensor(frame)
                
                tensor_list.append(hw_tensor)
                metadata_list.append(metadata)
                id_list.append(f"{source_id}_{timestamp:.2f}")

                # If batch size threshold reached, encode and write to Vector DB
                if len(tensor_list) >= batch_size:
                    self._store_batch_hardware(tensor_list, metadata_list, id_list, collection_name)
                    tensor_list, metadata_list, id_list = [], [], []

            count += 1

        cap.release()

        # Flush any remaining frames left in the buffer
        if tensor_list:
            self._store_batch_hardware(tensor_list, metadata_list, id_list, collection_name)

        print(f"✅ [Ingestion] Completed successfully for video source '{source_id}'.")


    def query(self, text_query: str,
              top_k: int = 5,
              min_timestamp: float | None = None,
              source_id: str | None = None,
              is_stream: bool = False,
              collection_name: str | None = None) -> dict:
        """
        Performs a semantic text search query against the ingested surveillance footage.
        """
        if collection_name is None:
            collection_name = self.COLLECTION_LIVE if is_stream else self.COLLECTION_UPLOADED

        # 1. Generate text query embedding vector
        query_vec = self.embedder.encode_text(text_query)

        # 2. Query Vector DB for matching frames that still exist on disk
        valid_frames = self.db.find_matching_frames(
            collection_name=collection_name,
            query_emb=query_vec.cpu().tolist(),
            top_k=top_k,
            min_timestamp=min_timestamp,
            source_id=source_id
        )

        if not valid_frames:
            return {"status": "error", "message": "No matches found."}

        # 3. Get VLM verification response
        response_text = self.vlm.verify_frames(text_query, valid_frames)
        timestamps = [m['timestamp'] for m in valid_frames]

        return {
            "status":      "success",
            "query":       text_query,
            "response":    response_text,
            "source_id":   valid_frames[0]['source_id'],
            "clip_start":  max(0, min(timestamps) - 2.0),
            "clip_end":    max(timestamps) + 2.0,
            "frame_path":  valid_frames[0]['frame_path'],
            "all_matches": valid_frames
        }


    def track_timeline(self, text_query: str,
                        top_k: int = 20,
                        max_distance: float = 2.0,
                        skip_vlm: bool = False) -> dict:
        """
        Traces a suspect or object's path across all cameras (cross-camera timeline tracking).
        """
        print(f"\n🕵️‍♂️ [Timeline] Tracing trajectory for query: '{text_query}'")

        # 1. Encode text query
        query_vec = self.embedder.encode_text(text_query)

        # 2. Build grouped trajectory timeline from DB collections
        timeline = self.db.build_trajectory(
            query_emb=query_vec.cpu().tolist(),
            top_k=top_k,
            max_distance=max_distance
        )

        if not timeline:
            return {"status": "error", "message": "Target not detected anywhere."}

        print(f"🕵️‍♂️ [Timeline] Constructed {len(timeline)} timeline nodes.")

        if skip_vlm:
            return {
                "status":         "success",
                "target":         text_query,
                "timeline_nodes": timeline,
            }

        # 3. Synthesize incident report via VLM
        incident_report = self.vlm.verify_timeline(text_query, timeline)

        return {
            "status":          "success",
            "target":          text_query,
            "incident_report": incident_report,
            "timeline_nodes":  timeline,
        }


    def find_suspect_by_image(self, suspect_image_path: str,
                              top_k: int = 5,
                              min_timestamp: float | None = None,
                              text_query: str | None = None) -> dict:
        """
        Performs reverse visual search matching a suspect mugshot against surveillance video collections.
        """
        print(f"\n🔍 [Visual Search] Mugshot: '{suspect_image_path}' + Context: '{text_query or 'None'}'")

        # 1. Extract visual features from suspect mugshot path
        img_vec = self.embedder.encode_image_path(suspect_image_path)
        if img_vec is None:
            return {
                "status":  "error",
                "message": f"Could not read suspect image: '{suspect_image_path}'"
            }

        # 2. Extract text features if textual context is provided
        text_vec = self.embedder.encode_text(text_query) if text_query else None

        # 3. Fuse visual and text vectors into a single search vector
        query_vec = fuse_modalities(img_vec, text_vec, image_weight=0.5)

        # 4. Search collections for valid frame matches
        valid_frames = self.db.find_suspect_frames(
            query_emb=query_vec.cpu().tolist(),
            top_k=top_k,
            min_timestamp=min_timestamp
        )

        if not valid_frames:
            return {"status": "error", "message": "Suspect not found in surveillance footage."}

        # 5. Use Gemini VLM for final facial recognition comparison
        response_text = self.vlm.verify_suspect(suspect_image_path, text_query, valid_frames)
        timestamps = [f["timestamp"] for f in valid_frames]

        return {
            "status":          "success",
            "query":           f"Mugshot + {text_query or 'Visual Only'}",
            "response":        response_text,
            "source_id":       valid_frames[0]['source_id'],
            "clip_start":      max(0, min(timestamps) - 2.0),
            "clip_end":        max(timestamps) + 2.0,
            "frame_path":      valid_frames[0]['frame_path'],
            "all_matches":     valid_frames
        }
