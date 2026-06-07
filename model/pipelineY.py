"""
pipeline.py — WatchTower.ai Unified ML Orchestration Engine
==========================================================
This file acts as the primary orchestrator for the WatchTower.ai machine learning engine.
It preserves the public API contract (the OfflineVideoPipeline class and all public method signatures)
to ensure compatibility with other backend layers.

Instead of containing all ML code in a single file, it coordinates:
- Embedder (model/embedder.py): Handles hardware-accelerated CLIP embedding generation.
- VectorDBManager (model/vectordb.py): Handles ChromaDB persistence, storage, and queries.
- VLMManager (model/vlm.py): Handles Gemini API validation, cache control, and frame downscaling.

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
    This class matches the exact signatures and attributes expected by the backend.
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
        """Delegates to Embedder module to convert numpy frame to preprocessed device tensor."""
        return self.embedder.convert_frame_to_tensor(frame_bgr)

    def _encode_image_tensor(self, tensor) -> "torch.Tensor":
        """Delegates to Embedder module to encode preprocessed image tensor to a CLIP embedding."""
        return self.embedder.encode_image_tensor(tensor)

    def _encode_text(self, text: str) -> "torch.Tensor":
        """Delegates to Embedder module to encode a search query text to a CLIP embedding."""
        return self.embedder.encode_text(text)

    def _store_batch_hardware(self, tensor_list: list, metadatas: list, ids: list, collection_name: str):
        """
        Extracts features from a list of frames using Embedder batch-encoding,
        and saves the resulting vectors to ChromaDB using the VectorDBManager.
        """
        if not tensor_list:
            return
        
        # 1. Batch encode image tensors on the device (MPS/CUDA/CPU)
        features_tensor = self.embedder.encode_image_batch(tensor_list)
        embeddings = features_tensor.cpu().tolist()

        # 2. Store embeddings, metadata, and IDs in the Vector DB
        self.db.add_embeddings(
            collection_name=collection_name,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    def _vlm_query(self, cache_key: str, contents: list) -> str:
        """Delegates to VLMManager to query Gemini with caching."""
        return self.vlm.query(cache_key, contents)

    def _resize_for_vlm(self, pil_img: Image.Image, max_side: int = 512) -> Image.Image:
        """Delegates to VLMManager to downsample image for cost saving."""
        return self.vlm.resize_for_vlm(pil_img, max_side)

    def _get_collection(self, collection_name: str):
        """Delegates to VectorDBManager to get/create a collection."""
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
        
        How it coordinates:
          - Decodes video frames via OpenCV (`cv2`).
          - Delegates frame image saving to disk via `self.io_pool` (async).
          - Delegates frame tensor preprocessing and embedding extraction to `self.embedder`.
          - Delegates vector storage to `self.db` (VectorDBManager).
        """
        if collection_name is None:
            collection_name = self.COLLECTION_UPLOADED

        # 1. Clear out previously saved frames to keep disk tidy
        frames_dir = f"./data/frames/{source_id}"
        if os.path.exists(frames_dir):
            print(f"🧹 [Ingestion] Cleaning old frames: {frames_dir}")
            shutil.rmtree(frames_dir)
        os.makedirs(frames_dir, exist_ok=True)

        # 2. Purge old vector database entries for this specific video source
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

        tensor_list = []
        metadata_list = []
        id_list = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Trigger optional callback for live stream UI updates
            if on_frame:
                on_frame(frame)

            # Sample frames based on target extraction FPS
            if count % frame_interval == 0:
                timestamp  = count / fps
                frame_path = f"./data/frames/{source_id}/t_{timestamp:.1f}.jpg"
                metadata   = {
                    "source_id": source_id,
                    "timestamp": timestamp,
                    "frame_path": frame_path
                }

                # Save frame as JPEG in background thread pool to prevent blocking frame extraction
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                self.io_pool.submit(pil_img.save, frame_path)

                # Preprocess OpenCV frame image on device (MPS/CUDA/CPU)
                hw_tensor = self.embedder.convert_frame_to_tensor(frame)
                
                tensor_list.append(hw_tensor)
                metadata_list.append(metadata)
                id_list.append(f"{source_id}_{timestamp:.2f}")

                # If batch size threshold reached, encode and write to Vector DB
                if len(tensor_list) >= batch_size:
                    self._store_batch_hardware(tensor_list, metadata_list, id_list, collection_name)
                    tensor_list = []
                    metadata_list = []
                    id_list = []

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
        Performs a semantic search query against the ingested surveillance footage.
        
        Workflow:
          1. Encodes text query via `Embedder`.
          2. Queries vector database collections using `VectorDBManager`.
          3. Checks if matching frames still exist on disk.
          4. Submits matches to the Gemini model via `VLMManager` for validation and synthesis.
        """
        if collection_name is None:
            collection_name = self.COLLECTION_LIVE if is_stream else self.COLLECTION_UPLOADED

        # 1. Generate text query embedding vector
        query_vec = self.embedder.encode_text(text_query)

        # 2. Build metadata filter matching teammate's database schema
        where_filter: dict = {}
        if min_timestamp is not None:
            where_filter["timestamp"] = {"$gte": min_timestamp}
        if source_id is not None:
            where_filter["source_id"] = source_id
        if not where_filter:
            where_filter = None

        # 3. Query Vector Database
        results = self.db.query(
            collection_name=collection_name,
            query_embedding=query_vec.cpu().tolist(),
            top_k=top_k,
            where_filter=where_filter
        )

        if not results['ids'] or not results['ids'][0]:
            return {"status": "error", "message": "No matches found."}

        raw_frames   = results['metadatas'][0]
        # Verify that the frame images are still present on disk
        valid_frames = [m for m in raw_frames if os.path.exists(m['frame_path'])]

        if not valid_frames:
            return {"status": "error", "message": "No valid image frames found on disk."}

        # 4. Synthesize contents for Gemini API (instructions + images)
        vlm_content = [
            f"Query: '{text_query}'. Analyze these CCTV frames and confirm if the target is present. "
            "Provide a professional 2-line summary. Mention the primary frame of detection clearly."
        ]
        for m in valid_frames:
            vlm_content.append(self.vlm.resize_for_vlm(Image.open(m['frame_path'])))

        timestamps = [m['timestamp'] for m in valid_frames]
        
        # 5. Get VLM verification response
        response_text = self.vlm.query(text_query, vlm_content)

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
        
        Workflow:
          1. Encodes search query text to a vector using `Embedder`.
          2. Iterates over all known vector collections (live, uploaded, default) to find matches.
          3. Rejects entries exceeding `max_distance` (where smaller distance = higher similarity).
          4. Deduplicates matching frames and groups them into chronological time blocks.
          5. Prompts Gemini VLM to synthesize a unified report outlining the suspect's movements.
        """
        print(f"\n🕵️‍♂️ [Timeline] Tracing trajectory for query: '{text_query}'")

        # 1. Encode text query
        query_vec = self.embedder.encode_text(text_query)

        # Search all active collections to find footage regardless of how it was ingested
        collections_to_search = list(dict.fromkeys([
            self.COLLECTION_UPLOADED,
            self.COLLECTION_LIVE,
            self.default_collection_name,
        ]))

        all_metadatas: list[dict] = []
        all_distances: list[float] = []

        # 2. Gather candidates from all database collections
        for cname in collections_to_search:
            try:
                results = self.db.query(
                    collection_name=cname,
                    query_embedding=query_vec.cpu().tolist(),
                    top_k=top_k
                )

                if results and results["ids"] and results["ids"][0]:
                    batch_meta = results["metadatas"][0]
                    batch_dist = results.get("distances", [[0.0] * len(batch_meta)])[0]
                    all_metadatas.extend(batch_meta)
                    all_distances.extend(batch_dist)
                    print(f"🕵️‍♂️ [Timeline] Found {len(batch_meta)} matches in [{cname}]")

            except Exception as e:
                print(f"⚠️ [Timeline] Error querying collection '{cname}': {e}")
                continue

        if not all_metadatas:
            return {"status": "error", "message": "Target not detected anywhere."}

        # 3. Filter candidates by distance and verify files exist on disk
        valid_frames = [
            {
                "source_id":  m["source_id"],
                "timestamp":  m["timestamp"],
                "frame_path": m["frame_path"],
                "distance":   d,
            }
            for m, d in zip(all_metadatas, all_distances)
            if d <= max_distance and os.path.exists(m["frame_path"])
        ]

        if not valid_frames:
            print(f"🕵️‍♂️ [Timeline] Candidates rejected. Minimum distance seen: {min(all_distances):.4f}")
            return {
                "status":  "error",
                "message": "No confident target locks. Try a more specific query.",
            }

        # Deduplicate matching frames by path
        seen: set[str] = set()
        deduped: list[dict] = []
        for f in valid_frames:
            if f["frame_path"] not in seen:
                seen.add(f["frame_path"])
                deduped.append(f)
        valid_frames = deduped

        # Sort matches chronologically
        valid_frames.sort(key=lambda x: x["timestamp"])

        # 4. Group matches into timeline blocks (if same camera and frame gap ≤ 60 seconds)
        timeline: list[dict] = []
        current_block: dict | None = None

        for frame in valid_frames:
            if current_block is None:
                current_block = {
                    "source_id":  frame["source_id"],
                    "start_time": frame["timestamp"],
                    "end_time":   frame["timestamp"],
                    "best_frame": frame["frame_path"],
                }
                continue

            same_cam  = frame["source_id"] == current_block["source_id"]
            close_gap = (frame["timestamp"] - current_block["end_time"]) <= 60.0

            if same_cam and close_gap:
                current_block["end_time"] = frame["timestamp"]
            else:
                timeline.append(current_block)
                current_block = {
                    "source_id":  frame["source_id"],
                    "start_time": frame["timestamp"],
                    "end_time":   frame["timestamp"],
                    "best_frame": frame["frame_path"],
                }

        if current_block:
            timeline.append(current_block)

        print(f"🕵️‍♂️ [Timeline] Constructed {len(timeline)} timeline nodes across {len({b['source_id'] for b in timeline})} camera(s).")

        if skip_vlm:
            return {
                "status":         "success",
                "target":         text_query,
                "timeline_nodes": timeline,
            }

        # 5. Synthesize a chronological report using Gemini VLM
        vlm_content = [
            "You are a master Surveillance Intelligence Agent specializing in cross-camera lineage tracking.",
            f"User request: '{text_query}'.",
            "Analyze every frame deeply. Synthesize a professional incident timeline detailing where the target went, "
            "what they were doing, and their visible behavior across zones. Act like a lead detective.",
        ]
        for idx, block in enumerate(timeline):
            vlm_content.append(
                f"Event {idx + 1} — Camera: {block['source_id']} | "
                f"Time window: {block['start_time']:.1f}s – {block['end_time']:.1f}s"
            )
            vlm_content.append(
                self.vlm.resize_for_vlm(Image.open(block["best_frame"]))
            )
        vlm_content.append(
            "Synthesize a strict, professional incident timeline detailing where the target went and what they were doing across these zones."
        )

        return {
            "status":          "success",
            "target":          text_query,
            "incident_report": self.vlm.query(text_query, vlm_content),
            "timeline_nodes":  timeline,
        }


    def find_suspect_by_image(self, suspect_image_path: str,
                              top_k: int = 5,
                              min_timestamp: float | None = None,
                              text_query: str | None = None) -> dict:
        """
        Performs reverse visual search matching a suspect mugshot against surveillance video collections.
        
        Workflow:
          1. Loads visual image.
          2. Preprocesses and encodes mugshot to visual embedding via `Embedder`.
          3. Optionally encodes text query to textual embedding.
          4. Fuses visual and text embeddings via vector arithmetic mean to construct the search query.
          5. Queries database collections using `VectorDBManager`.
          6. Submits matches to the Gemini model via `VLMManager` for facial recognition verification.
        """
        print(f"\n🔍 [Visual Search] Mugshot: '{suspect_image_path}' + Context: '{text_query or 'None'}'")

        # 1. Load the suspect reference mugshot image
        bgr_frame = cv2.imread(suspect_image_path)
        if bgr_frame is None:
            return {
                "status":  "error",
                "message": f"Could not read suspect image: '{suspect_image_path}'"
            }

        # 2. Extract visual features using CLIP on the active hardware device
        hw_tensor = self.embedder.convert_frame_to_tensor(bgr_frame)
        img_vec   = self.embedder.encode_image_tensor(hw_tensor)

        # 3. Extract text features if textual context is provided
        text_vec = self.embedder.encode_text(text_query) if text_query else None

        # 4. Fuse visual and text vectors into a single unified search vector
        query_vec = fuse_modalities(img_vec, text_vec, image_weight=0.5)

        # 5. Query active database collections
        where_filter = {"timestamp": {"$gte": min_timestamp}} if min_timestamp else None
        results = None

        # Iterate over collections to find the suspect in either live streams or uploaded vaults
        for cname in [self.COLLECTION_UPLOADED, self.COLLECTION_LIVE, self.default_collection_name]:
            r = self.db.query(
                collection_name=cname,
                query_embedding=query_vec.cpu().tolist(),
                top_k=top_k,
                where_filter=where_filter
            )
            if r['ids'] and r['ids'][0]:
                results = r
                break

        if results is None or not results['ids'] or not results['ids'][0]:
            return {"status": "error", "message": "Suspect not found in surveillance footage."}

        metadatas = results['metadatas'][0]
        distances = results.get('distances', [[0.0] * len(metadatas)])[0]

        # 6. Verify that matched frame images exist on disk
        valid_frames = [
            {
                "source_id":  m["source_id"],
                "timestamp":  m["timestamp"],
                "frame_path": m["frame_path"],
                "distance":   d
            }
            for m, d in zip(metadatas, distances)
            if os.path.exists(m["frame_path"])
        ]

        if not valid_frames:
            return {"status": "error", "message": "No valid matching frames on disk."}

        # 7. Use Gemini VLM for final facial recognition comparison
        suspect_pil = Image.open(suspect_image_path).convert("RGB")
        vlm_content = [
            "You are a strict security facial recognition and object-matching AI Agent.",
            f"User Context: {text_query if text_query else 'General identification only.'}",
            "Compare the suspect reference image to the CCTV frames.",
            "State MATCH CONFIRMED or NO MATCH followed by a professional 2-line summary.",
            self.vlm.resize_for_vlm(suspect_pil),
            "DATABASE VISUAL RETURNS:"
        ]
        # Include top 3 visual search frame returns
        for m in valid_frames[:3]:
            vlm_content.append(self.vlm.resize_for_vlm(Image.open(m['frame_path'])))

        cache_key = f"{suspect_image_path}_{text_query or ''}"
        timestamps = [f["timestamp"] for f in valid_frames]

        response_text = self.vlm.query(cache_key, vlm_content)

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
