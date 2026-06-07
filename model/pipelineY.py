"""
pipeline.py — WatchTower.ai Unified ML Engine
==============================================
Merges:
  Hardware acceleration (device-side preprocessing)
  find_suspect_by_image now fully hardware-accelerated with multimodal vector fusion
  All IO-bound VLM calls cached and images resized before send (quota saving)
"""

import os
import sys
import time
import shutil
import concurrent.futures
import hashlib

import cv2
import torch
import torchvision.transforms.v2 as T
import chromadb
import open_clip
from PIL import Image
from google import genai

# Allow OpenCV/FFmpeg to connect to IP cameras with self-signed HTTPS certs
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "tls_verify;0"


# ──────────────────────────────────────────────────────────────────────────────
# 1.  Vector Modality Fusion (Pure PyTorch Vectorized)
# ──────────────────────────────────────────────────────────────────────────────
def _fuse_modalities(image_vec: "torch.Tensor",
                     text_vec: "torch.Tensor | None",
                     image_weight: float = 0.5) -> "torch.Tensor":
    """
    Weighted multimodal fusion + L2 renormalization using standard PyTorch.
    Returns image_vec unchanged if text_vec is None.
    """
    if text_vec is None:
        return image_vec
    with torch.no_grad():
        fused  = image_weight * image_vec + (1.0 - image_weight) * text_vec
        fused /= fused.norm(dim=-1, keepdim=True)
    return fused


# ──────────────────────────────────────────────────────────────────────────────
# 4.  Main Pipeline
# ──────────────────────────────────────────────────────────────────────────────
class OfflineVideoPipeline:

    # ── Collection routing (matches teammate's backend contract) ──────────────
    COLLECTION_LIVE     = "live_cctv_stream"
    COLLECTION_UPLOADED = "uploaded_vault"

    def __init__(self, api_key: str,
                 collection_name: str = "cctv_main_stream"):

        # ── Hardware dispatch ────────────────────────────────────────────────
        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        print(f"\n🧠 Hardware locked → [{self.device.upper()}]")
        if self.device == "cuda":
            props = torch.cuda.get_device_properties(0)
            print(f"   GPU : {props.name}  |  VRAM: {props.total_memory // 1024**2} MB")

        # ── CLIP ─────────────────────────────────────────────────────────────
        self.model, _, _ = open_clip.create_model_and_transforms(
            'ViT-B-32', pretrained='openai'     
        )
        self.model = self.model.to(self.device).eval()
        self.tokenizer = open_clip.get_tokenizer('ViT-B-32')
        # ── Device-side preprocessing ────────────────────────────────────────────
        self.device_preprocess = T.Compose([
            T.Resize(224, antialias=True),
            T.CenterCrop(224),
            T.Normalize(
                mean=(0.48145466, 0.4578275,  0.40821073),
                std= (0.26862954, 0.26130258, 0.27577711)
            )
        ])

        # ── Vector DB ────────────────────────────────────────────────────────
        os.makedirs("./data/vector_db", exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path="./data/vector_db")

        # Pre-create all known collections (cosine space for CLIP vectors)
        for cname in [collection_name, self.COLLECTION_LIVE, self.COLLECTION_UPLOADED]:
            self.chroma_client.get_or_create_collection(
                name=cname, metadata={"hnsw:space": "cosine"}
            )

        # Default collection (for track_timeline which has no is_stream context)
        self.default_collection_name = collection_name

        # ── VLM ──────────────────────────────────────────────────────────────
        self.vlm_client     = genai.Client(api_key=api_key)
        self.vlm_model_name = "gemini-2.5-flash"
        self._vlm_cache: dict[str, str] = {}

        # ── Async I/O pool ───────────────────────────────────────────────────
        self.io_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)



    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _convert_cv2_to_hardware_tensor(self, frame_bgr) -> torch.Tensor:
        """BGR numpy frame → normalised CHW float tensor on device."""
        hw = torch.from_numpy(frame_bgr).permute(2, 0, 1).float().to(self.device)
        hw = hw[[2, 1, 0], ...] / 255.0
        return self.device_preprocess(hw)

    def _encode_image_tensor(self, tensor: torch.Tensor) -> torch.Tensor:
        """Single preprocessed CHW tensor → normalised [D] vec on device."""
        with torch.no_grad():
            feat = self.model.encode_image(tensor.unsqueeze(0))
            feat /= feat.norm(dim=-1, keepdim=True)
        return feat.squeeze(0)

    def _encode_text(self, text: str) -> torch.Tensor:
        """Text string → normalised [D] vec on device."""
        tokens = self.tokenizer([text]).to(self.device)
        with torch.no_grad():
            feat = self.model.encode_text(tokens)
            feat /= feat.norm(dim=-1, keepdim=True)
        return feat.squeeze(0)

    def _store_batch_hardware(self, tensor_list: list,
                              metadatas: list, ids: list,
                              collection_name: str):
        """
        Stacks device tensors, CLIP-encodes, and upserts to ChromaDB.
        """
        if not tensor_list:
            return
        tensors = torch.stack(tensor_list).to(self.device)
        with torch.no_grad():
            features = self.model.encode_image(tensors)
            features /= features.norm(dim=-1, keepdim=True)

        col = self.chroma_client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        col.add(embeddings=features.cpu().tolist(), metadatas=metadatas, ids=ids)
        print(f"💾 Stored {len(tensor_list)} frames → [{collection_name}] | total: {col.count()}")

    def _vlm_query(self, cache_key: str, contents: list) -> str:
        """VLM call with MD5-keyed cache to save quota."""
        h = hashlib.md5(cache_key.encode()).hexdigest()
        if h in self._vlm_cache:
            print("[VLM] Cache hit — skipping API call.")
            return self._vlm_cache[h]
        resp = self.vlm_client.models.generate_content(
            model=self.vlm_model_name, contents=contents
        )
        self._vlm_cache[h] = resp.text
        return resp.text

    def _resize_for_vlm(self, pil_img: Image.Image,
                         max_side: int = 512) -> Image.Image:
        """Downscale before VLM send — reduces token cost."""
        pil_img.thumbnail((max_side, max_side), Image.LANCZOS)
        return pil_img

    def _get_collection(self, collection_name: str):
        return self.chroma_client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )


    def ingest_video(self, video_path: str, source_id: str,
                     collection_name: str = None,
                     fps_to_extract: int = 1,
                     batch_size: int = 32,
                     on_frame=None):
        """
        Reads a recorded video file, preprocesses frames on the active device,
        and encodes them in batches synchronously.

        on_frame: optional callback(bgr_frame) — called on every decoded frame
                  so the backend can stream latest frames to the UI via asyncio.
        collection_name: defaults to COLLECTION_UPLOADED to match teammate's routing.
        """
        if collection_name is None:
            collection_name = self.COLLECTION_UPLOADED

        # Fresh-start cleanup (teammate requirement)
        frames_dir = f"./data/frames/{source_id}"
        if os.path.exists(frames_dir):
            print(f"🧹 Cleaning old frames: {frames_dir}")
            shutil.rmtree(frames_dir)
        os.makedirs(frames_dir, exist_ok=True)

        try:
            col = self._get_collection(collection_name)
            col.delete(where={"source_id": source_id})
            print(f"🧹 Purged old VectorDB entries for {source_id} in [{collection_name}]")
        except Exception:
            pass

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ Could not open video: {video_path}")
            return

        fps            = round(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        frame_interval = max(1, int(fps / fps_to_extract))
        count          = 0

        print(f"📼 Ingesting '{video_path}' → [{collection_name}] on [{self.device.upper()}]")

        tensor_list = []
        metadata_list = []
        id_list = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if on_frame:
                on_frame(frame)

            if count % frame_interval == 0:
                timestamp  = count / fps
                frame_path = f"./data/frames/{source_id}/t_{timestamp:.1f}.jpg"
                metadata   = {
                    "source_id": source_id,
                    "timestamp": timestamp,
                    "frame_path": frame_path
                }

                # Save frame image asynchronously to disk
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                self.io_pool.submit(pil_img.save, frame_path)

                # Preprocess frame tensor
                hw_tensor = self._convert_cv2_to_hardware_tensor(frame)
                tensor_list.append(hw_tensor)
                metadata_list.append(metadata)
                id_list.append(f"{source_id}_{timestamp:.2f}")

                if len(tensor_list) >= batch_size:
                    self._store_batch_hardware(tensor_list, metadata_list, id_list, collection_name)
                    tensor_list = []
                    metadata_list = []
                    id_list = []

            count += 1

        cap.release()

        # Flush any remaining frames
        if tensor_list:
            self._store_batch_hardware(tensor_list, metadata_list, id_list, collection_name)

        print(f"✅ Ingest done for {source_id}.")

    # ──────────────────────────────────────────────────────────────────────────
    # Query — text → CCTV search
    # ──────────────────────────────────────────────────────────────────────────

    def query(self, text_query: str,
              top_k: int = 5,
              min_timestamp: float | None = None,
              source_id: str | None = None,
              is_stream: bool = False,
              collection_name: str | None = None) -> dict:
        """
        Text query → top-k retrieval → VLM verification.
        Signature matches teammate's backend contract exactly.
        Routes to live vs uploaded collection based on is_stream flag.
        """
        if collection_name is None:
            collection_name = self.COLLECTION_LIVE if is_stream else self.COLLECTION_UPLOADED

        query_vec = self._encode_text(text_query)   # on device

        # Build where filter (teammate's source_id + timestamp filters)
        where_filter: dict = {}
        if min_timestamp is not None:
            where_filter["timestamp"] = {"$gte": min_timestamp}
        if source_id is not None:
            where_filter["source_id"] = source_id
        if not where_filter:
            where_filter = None

        col = self._get_collection(collection_name)
        results = col.query(
            query_embeddings=[query_vec.cpu().tolist()],
            n_results=top_k,
            where=where_filter
        )

        if not results['ids'] or not results['ids'][0]:
            return {"status": "error", "message": "No matches found."}

        raw_frames   = results['metadatas'][0]
        # File-existence guard (teammate requirement)
        valid_frames = [m for m in raw_frames if os.path.exists(m['frame_path'])]

        if not valid_frames:
            return {"status": "error", "message": "No valid image frames found on disk."}

        vlm_content = [
            f"Query: '{text_query}'. Analyze these CCTV frames and confirm if the target is present. "
            "Provide a professional 2-line summary. Mention the primary frame of detection clearly."
        ]
        for m in valid_frames:
            vlm_content.append(self._resize_for_vlm(Image.open(m['frame_path'])))

        timestamps = [m['timestamp'] for m in valid_frames]
        return {
            "status":      "success",
            "query":       text_query,
            "response":    self._vlm_query(text_query, vlm_content),
            "source_id":   valid_frames[0]['source_id'],
            "clip_start":  max(0, min(timestamps) - 2.0),
            "clip_end":    max(timestamps) + 2.0,
            "frame_path":  valid_frames[0]['frame_path'],
            "all_matches": valid_frames
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Timeline tracker — cross-camera detective mode
    # ──────────────────────────────────────────────────────────────────────────

    def track_timeline(self, text_query: str,
                       top_k: int = 20,
                       max_distance: float = 2.0,
                       skip_vlm: bool = False) -> dict:
        """
        Maps target movement across all cameras.
        Searches UPLOADED, LIVE, and default collections so footage
        ingested via any path is always found.
        max_distance=2.0 matches teammate's high-recall setting (VLM does final verify).
        skip_vlm=True for fast dev iteration without burning quota.
        """
        print(f"\n[TRACING] Computing trajectory for '{text_query}'")

        query_vec = self._encode_text(text_query)

        # ── Search ALL populated collections, not just the default empty one ──
        collections_to_search = list(dict.fromkeys([
            self.COLLECTION_UPLOADED,       # "uploaded_vault"   ← videos land here
            self.COLLECTION_LIVE,           # "live_cctv_stream" ← streams land here
            self.default_collection_name,   # "cctv_main_stream" ← legacy / manual
        ]))

        all_metadatas: list[dict] = []
        all_distances: list[float] = []

        for cname in collections_to_search:
            try:
                col = self._get_collection(cname)
                if col.count() == 0:
                    print(f"[TRACING] Skipping empty collection: [{cname}]")
                    continue

                print(f"[TRACING] Searching [{cname}] ({col.count()} frames)...")

                results = col.query(
                    query_embeddings=[query_vec.cpu().tolist()],
                    n_results=min(top_k, col.count()),
                    include=["metadatas", "distances"]
                )

                if results and results["ids"] and results["ids"][0]:
                    batch_meta = results["metadatas"][0]
                    batch_dist = results.get(
                        "distances",
                        [[0.0] * len(batch_meta)]
                    )[0]
                    all_metadatas.extend(batch_meta)
                    all_distances.extend(batch_dist)
                    print(f"[TRACING] Found {len(batch_meta)} candidates in [{cname}]")

            except Exception as e:
                print(f"[TRACING] Skipping collection '{cname}': {e}")
                continue

        if not all_metadatas:
            return {"status": "error", "message": "Target not detected anywhere."}

        # ── Distance + file-existence guard ───────────────────────────────────
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
            # Distance filter might be too tight — log what we actually got
            print(f"[TRACING] All {len(all_metadatas)} candidates filtered out. "
                  f"Min distance seen: {min(all_distances):.4f}")
            return {
                "status":  "error",
                "message": "No confident/existing target locks. "
                           "Try a more specific query or re-upload the footage.",
            }

        # ── Deduplicate by frame_path (same frame can appear in multiple searches) ──
        seen: set[str] = set()
        deduped: list[dict] = []
        for f in valid_frames:
            if f["frame_path"] not in seen:
                seen.add(f["frame_path"])
                deduped.append(f)
        valid_frames = deduped

        # Sort chronologically
        valid_frames.sort(key=lambda x: x["timestamp"])

        # ── Compress into timeline blocks (same camera, gap ≤ 60 s) ──────────
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

        print(f"[TRACING] Timeline built: {len(timeline)} node(s) across "
              f"{len({b['source_id'] for b in timeline})} camera(s)")

        if skip_vlm:
            return {
                "status":         "success",
                "target":         text_query,
                "timeline_nodes": timeline,
            }

        # ── VLM synthesis ─────────────────────────────────────────────────────
        vlm_content = [
            "You are a master Surveillance Intelligence Agent specializing in "
            "cross-camera lineage tracking.",
            f"User request: '{text_query}'.",
            "Analyze every frame deeply. Synthesize a professional incident timeline "
            "detailing where the target went, what they were doing, and their visible "
            "behavior across zones. Act like a lead detective.",
        ]
        for idx, block in enumerate(timeline):
            vlm_content.append(
                f"Event {idx + 1} — Camera: {block['source_id']} | "
                f"Time window: {block['start_time']:.1f}s – {block['end_time']:.1f}s"
            )
            vlm_content.append(
                self._resize_for_vlm(Image.open(block["best_frame"]))
            )
        vlm_content.append(
            "Synthesize a strict, professional incident timeline detailing "
            "where the target went and what they were doing across these zones."
        )

        return {
            "status":          "success",
            "target":          text_query,
            "incident_report": self._vlm_query(text_query, vlm_content),
            "timeline_nodes":  timeline,
        }


    # ──────────────────────────────────────────────────────────────────────────
    # Reverse image search — hardware-accelerated with multimodal fusion
    # ──────────────────────────────────────────────────────────────────────────

    def find_suspect_by_image(self, suspect_image_path: str,
                              top_k: int = 5,
                              min_timestamp: float | None = None,
                              text_query: str | None = None) -> dict:
        """
        Multi-modal reverse image search.
        Signature matches teammate's API contract (text_query param for context fusion).

        Pipeline:
          1. cv2.imread → BGR tensor on device   (IO + device preprocessing)
          2. CLIP image encode                   (device)
          3. Optional text encode                (device)
          4. _fuse_modalities                    (weighted mean on device, re-normalise)
          5. ChromaDB query                      (cached cosine search)
          6. VLM verification with resized imgs  (IO — cached)
        """
        print(f"\n[REVERSE IMAGE SEARCH] Visual query: '{suspect_image_path}' "
              f"+ context: '{text_query}'")

        # ── IO: load suspect image ───────────────────────────────────────────
        bgr_frame = cv2.imread(suspect_image_path)
        if bgr_frame is None:
            return {
                "status":  "error",
                "message": f"Could not read suspect image: '{suspect_image_path}'"
            }

        # ── Device: image preprocessing + encoding ────────────────────────────
        hw_tensor   = self._convert_cv2_to_hardware_tensor(bgr_frame)   # device
        img_vec     = self._encode_image_tensor(hw_tensor)               # device [D]

        # ── Device: optional text encode ───────────────────────────────────────
        text_vec = self._encode_text(text_query) if text_query else None  # device [D]

        # ── Device: multimodal fusion ────────────────────────────────────
        # Equal weight (0.5/0.5) matches teammate's arithmetic mean fusion.
        query_vec = _fuse_modalities(img_vec, text_vec, image_weight=0.5)

        # ── Search ────────────────────────────────────────────────────────────
        where_filter = {"timestamp": {"$gte": min_timestamp}} if min_timestamp else None

        # Try both collections — suspect could be in live OR uploaded footage
        results = None
        for cname in [self.COLLECTION_UPLOADED, self.COLLECTION_LIVE,
                      self.default_collection_name]:
            col = self._get_collection(cname)
            r   = col.query(
                query_embeddings=[query_vec.cpu().tolist()],
                n_results=top_k,
                where=where_filter,
                include=["metadatas", "distances"]
            )
            if r['ids'] and r['ids'][0]:
                results = r
                break

        if results is None or not results['ids'] or not results['ids'][0]:
            return {"status": "error", "message": "Suspect not found in surveillance footage."}

        metadatas = results['metadatas'][0]
        distances = results.get('distances', [[0.0] * len(metadatas)])[0]

        # ── File-existence guard ──────────────────────────────────────────────
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
            return {"status": "error",
                    "message": "No valid frames on disk for this suspect photo."}

        # ── VLM verification (IO-bound — cached + resized) ────────────────────
        # PIL only for VLM — Gemini API requires PIL images
        suspect_pil = Image.open(suspect_image_path).convert("RGB")

        vlm_content = [
            "You are a strict security facial recognition and object-matching AI Agent.",
            f"User Context: {text_query if text_query else 'General identification only.'}",
            "Compare the suspect reference image to the CCTV frames.",
            "State MATCH CONFIRMED or NO MATCH followed by a professional 2-line summary.",
            self._resize_for_vlm(suspect_pil),
            "DATABASE VISUAL RETURNS:"
        ]
        for m in valid_frames[:3]:
            vlm_content.append(self._resize_for_vlm(Image.open(m['frame_path'])))

        cache_key = f"{suspect_image_path}_{text_query or ''}"
        timestamps = [f["timestamp"] for f in valid_frames]

        return {
            "status":          "success",
            "query":           f"Mugshot + {text_query or 'Visual Only'}",
            "response":        self._vlm_query(cache_key, vlm_content),
            "source_id":       valid_frames[0]['source_id'],
            "clip_start":      max(0, min(timestamps) - 2.0),
            "clip_end":        max(timestamps) + 2.0,
            "frame_path":      valid_frames[0]['frame_path'],
            "all_matches":     valid_frames
        }
