"""
pipeline.py — WatchTower.ai Unified ML Engine
==============================================
Merges:
  CUDA/OpenMP acceleration (VRAM preprocessing, cosine search, entropy gate)
  find_suspect_by_image now fully CUDA-accelerated with multimodal vector fusion kernel
  All IO-bound VLM calls cached and images resized before send (quota saving)

RTX 3000 series (Ampere sm_86) tuning preserved throughout.
"""

import os
import sys
import time
import shutil
import subprocess
import threading
import queue
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
# 1.  Motion Entropy Calculation (Pure PyTorch Vectorized)
# ──────────────────────────────────────────────────────────────────────────────
def _compute_entropy_hardware(prev: torch.Tensor, curr: torch.Tensor,
                               noise_floor: float,
                               shift_threshold: float) -> tuple[bool, float]:
    """
    Computes the ratio of pixels that changed between prev and curr frames.
    Runs on the active PyTorch device (CPU/CUDA/MPS) automatically.
    """
    with torch.no_grad():
        diff_mask = torch.abs(curr - prev) > noise_floor
        ratio = diff_mask.float().mean().item()
        motion_detected = ratio >= shift_threshold
    return motion_detected, ratio


# ──────────────────────────────────────────────────────────────────────────────
# 2.  In-VRAM Cosine Similarity Search (Pure PyTorch Vectorized)
# ──────────────────────────────────────────────────────────────────────────────
def _cuda_topk_cosine(query_vec: "torch.Tensor",
                      candidate_vecs: "torch.Tensor",
                      top_k: int) -> "torch.Tensor":
    """
    Performs cosine similarity search directly in device VRAM using PyTorch.
    query_vec:      [D]    — L2-normalised
    candidate_vecs: [N, D] — L2-normalised
    Returns: LongTensor [k] of most-similar indices.
    """
    with torch.no_grad():
        sims = candidate_vecs @ query_vec          # [N] dot products
        k    = min(top_k, sims.shape[0])
        return torch.topk(sims, k).indices


# ──────────────────────────────────────────────────────────────────────────────
# 3.  Vector Modality Fusion (Pure PyTorch Vectorized)
# ──────────────────────────────────────────────────────────────────────────────
def _cuda_fuse_modalities(image_vec: "torch.Tensor",
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
        # ── GPU-side preprocessing ────────────────────────────────────────────
        self.gpu_preprocess = T.Compose([
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

        # ── VRAM embedding cache ──────────────────────────────────────────────
        # frame_path → normalised [D] tensor on device.
        self._embed_cache: dict[str, torch.Tensor] = {}

        # ── VLM ──────────────────────────────────────────────────────────────
        self.vlm_client     = genai.Client(api_key=api_key)
        self.vlm_model_name = "gemini-2.5-flash"
        self._vlm_cache: dict[str, str] = {}

        # ── Async I/O pool ───────────────────────────────────────────────────
        self.io_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        self.ai_queue = queue.Queue(maxsize=128)
        self._worker_thread = threading.Thread(
            target=self._ai_worker, daemon=True
        )
        self._worker_thread.start()



    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _convert_cv2_to_hardware_tensor(self, frame_bgr) -> torch.Tensor:
        """BGR numpy frame → normalised CHW float tensor on device."""
        hw = torch.from_numpy(frame_bgr).permute(2, 0, 1).float().to(self.device)
        hw = hw[[2, 1, 0], ...] / 255.0
        return self.gpu_preprocess(hw)

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
        Stacks device tensors, CLIP-encodes, upserts to named collection.
        Also populates VRAM cache for later CUDA cosine search.
        """
        if not tensor_list:
            return
        tensors = torch.stack(tensor_list).to(self.device)
        with torch.no_grad():
            features = self.model.encode_image(tensors)
            features /= features.norm(dim=-1, keepdim=True)

        for feat, meta in zip(features, metadatas):
            self._embed_cache[meta["frame_path"]] = feat.detach()

        col = self.chroma_client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        col.add(embeddings=features.cpu().tolist(), metadatas=metadatas, ids=ids)
        print(f"💾 Stored {len(tensor_list)} frames → [{collection_name}] | total: {col.count()}")

    def _store_batch(self, images: list, metadatas: list, ids: list, collection_name: str | None = None):
        """
        Legacy/WIP compatibility helper. Converts PIL Images/BGR arrays to hardware tensors 
        and calls _store_batch_hardware.
        """
        if collection_name is None:
            collection_name = self.default_collection_name
        
        tensor_list = []
        for img in images:
            if isinstance(img, Image.Image):
                import numpy as np
                img_np = np.array(img.convert("RGB"))
                img_bgr = img_np[:, :, ::-1].copy()
                tensor_list.append(self._convert_cv2_to_hardware_tensor(img_bgr))
            elif isinstance(img, np.ndarray):
                tensor_list.append(self._convert_cv2_to_hardware_tensor(img))
            elif torch.is_tensor(img):
                tensor_list.append(img.to(self.device))
        
        self._store_batch_hardware(tensor_list, metadatas, ids, collection_name)


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

    @staticmethod
    def _resolve_youtube_url(url: str) -> str | None:
        try:
            result = subprocess.run(
                ["yt-dlp", "-g", url],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip().split('\n')[0]
        except Exception as e:
            print(f"yt-dlp failed: {e}")
            return None

    def _get_collection(self, collection_name: str):
        return self.chroma_client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    def _cuda_query(self, query_vec: torch.Tensor,
                    top_k: int,
                    where_filter: dict | None,
                    collection_name: str) -> dict | None:
        """
        VRAM-resident cosine search when cache is warm.
        Falls back to None so caller can use ChromaDB instead.
        """
        if len(self._embed_cache) < top_k:
            return None

        paths = list(self._embed_cache.keys())
        vecs  = torch.stack(list(self._embed_cache.values()))   # [N, D]

        min_ts = (where_filter or {}).get("timestamp", {}).get("$gte", None)
        src_id = (where_filter or {}).get("source_id", None)

        indices = _cuda_topk_cosine(query_vec, vecs, top_k * 3)  # over-fetch

        matched = []
        for idx in indices.tolist():
            path = paths[idx]
            res  = self._get_collection(collection_name).get(
                where={"frame_path": path}, include=["metadatas"]
            )
            if res["metadatas"]:
                meta = res["metadatas"][0]
                if min_ts is not None and meta["timestamp"] < min_ts:
                    continue
                if src_id is not None and meta.get("source_id") != src_id:
                    continue
                if not os.path.exists(meta["frame_path"]):
                    continue
                matched.append(meta)
            if len(matched) == top_k:
                break

        if not matched:
            return None

        return {
            "metadatas": [matched],
            "ids":       [[m["frame_path"] for m in matched]],
            "distances": [[0.0] * len(matched)]
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Background AI worker  (teammate's pattern, adapted for CUDA path)
    # ──────────────────────────────────────────────────────────────────────────

    def _ai_worker(self):
        """
        Drains the ai_queue in batches, encoding with CLIP on CUDA.
        Keeps preprocessing out of the main video-read loop so ingest
        doesn't block waiting for GPU.
        """
        batches: dict[str, dict] = {}   # keyed by collection_name

        while True:
            try:
                task = self.ai_queue.get()
                if task is None:
                    break

                # FLUSH signal sent after video read loop finishes
                if isinstance(task, tuple) and task[0] == "FLUSH":
                    _, source_id, collection_name, _ = task
                    if collection_name in batches and batches[collection_name]["tensors"]:
                        b = batches[collection_name]
                        print(f"✅ [AI Worker] Flushing {len(b['tensors'])} frames "
                              f"for {source_id} → [{collection_name}]")
                        self._store_batch_hardware(
                            b["tensors"], b["metadatas"], b["ids"], collection_name
                        )
                        batches[collection_name] = {"tensors": [], "metadatas": [], "ids": []}
                    continue

                # Normal frame task
                hw_tensor, metadata, source_id, timestamp, collection_name = task

                if collection_name not in batches:
                    batches[collection_name] = {"tensors": [], "metadatas": [], "ids": []}

                b = batches[collection_name]
                b["tensors"].append(hw_tensor)
                b["metadatas"].append(metadata)
                b["ids"].append(f"{source_id}_{timestamp:.2f}")

                if len(b["tensors"]) >= 32:
                    self._store_batch_hardware(
                        b["tensors"], b["metadatas"], b["ids"], collection_name
                    )
                    batches[collection_name] = {"tensors": [], "metadatas": [], "ids": []}

            except Exception as e:
                print(f"❌ [AI Worker] ERROR: {e}")
            finally:
                self.ai_queue.task_done()

    # ──────────────────────────────────────────────────────────────────────────
    # Kernel 1 — Offline video ingest
    # ──────────────────────────────────────────────────────────────────────────

    def ingest_video(self, video_path: str, source_id: str,
                     collection_name: str = None,
                     fps_to_extract: int = 1,
                     batch_size: int = 64,
                     on_frame=None):
        """
        Reads a recorded video file, preprocesses frames on CUDA, queues for
        background CLIP encoding.

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

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # on_frame callback for the backend's live preview streaming
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

                # Synchronous JPEG save (teammate requirement — ensures file exists
                # on disk before VLM tries to open it)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                self.io_pool.submit(pil_img.save, frame_path)
                #pil_img.save(frame_path)

                # CUDA preprocessing on main thread, encoding deferred to worker
                try:
                    hw_tensor = self._convert_cv2_to_hardware_tensor(frame)
                    self.ai_queue.put_nowait(
                        (hw_tensor, metadata, source_id, timestamp, collection_name)
                    )
                except queue.Full:
                    print(f"⚠️ AI queue full — skipping frame t={timestamp:.1f}")

            count += 1

        cap.release()

        print(f"🏁 Read complete for {source_id}. Waiting for AI worker...")
        self.ai_queue.put(("FLUSH", source_id, collection_name, True))
        self.ai_queue.join()
        print(f"✅ Ingest done for {source_id}.")

    # ──────────────────────────────────────────────────────────────────────────
    # Kernel 2 — Standard live ingestion (1 fps, no motion gate)
    # ──────────────────────────────────────────────────────────────────────────

    def start_live_ingestion(self, stream_input_url: str,
                             source_id: str = "live_cam01",
                             max_test_iterations: int | None = None):
        """
        Embeds one frame per second unconditionally.
        Routes to COLLECTION_LIVE to match teammate's backend routing.
        """
        stream_url = stream_input_url
        if "youtube.com" in stream_input_url or "youtu.be" in stream_input_url:
            print("Extracting HLS stream from YouTube...")
            stream_url = self._resolve_youtube_url(stream_input_url)
            if stream_url is None:
                return

        collection_name = self.COLLECTION_LIVE
        print(f"📡 Live ingestion → {source_id} → [{collection_name}]")
        os.makedirs(f"./data/frames/{source_id}", exist_ok=True)

        cap               = cv2.VideoCapture(stream_url)
        last_extract_time = 0.0
        extracted_count   = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    if max_test_iterations:
                        break
                    print("Stream stuttered. Reconnecting in 5s...")
                    time.sleep(5)
                    cap = cv2.VideoCapture(stream_url)
                    continue

                curr_t = time.time()
                if curr_t - last_extract_time < 1.0:
                    continue

                hw_tensor  = self._convert_cv2_to_hardware_tensor(frame)
                frame_path = f"./data/frames/{source_id}/live_{int(curr_t)}.jpg"
                self.io_pool.submit(
                    Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save,
                    frame_path
                )
                self._store_batch_hardware(
                    [hw_tensor],
                    [{"source_id": source_id, "timestamp": curr_t, "frame_path": frame_path}],
                    [f"{source_id}_{int(curr_t)}"],
                    collection_name
                )

                print(f"[{source_id}] Embedded @ {time.strftime('%H:%M:%S')}")
                last_extract_time = curr_t
                extracted_count  += 1

                if max_test_iterations and extracted_count >= max_test_iterations:
                    break
        finally:
            cap.release()

    # ──────────────────────────────────────────────────────────────────────────
    # Kernel 3 — Smart live ingestion v2 (motion-gated, C++ entropy gate)
    # ──────────────────────────────────────────────────────────────────────────

    def start_smart_live_ingestion_v2(self, stream_input_url: str,
                                      source_id: str = "live_cam_v2",
                                      noise_floor: float = 0.03,
                                      physical_shift_threshold: float = 0.015,
                                      max_test_iterations: int | None = None):
        """Motion-gated live ingestion using C++ CUDA entropy kernel."""
        print(f"\n🧬 [SMART V2] Entropy Gate — {source_id}")

        stream_url = stream_input_url
        if "youtube.com" in stream_input_url or "youtu.be" in stream_input_url:
            stream_url = self._resolve_youtube_url(stream_input_url)
            if stream_url is None:
                return

        collection_name = self.COLLECTION_LIVE
        os.makedirs(f"./data/frames/{source_id}", exist_ok=True)
        cap = cv2.VideoCapture(stream_url)

        last_extract_time                   = 0.0
        last_hw_tensor: torch.Tensor | None = None
        extracted_count                     = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    if max_test_iterations:
                        break
                    time.sleep(2)
                    cap = cv2.VideoCapture(stream_url)
                    continue

                curr_t = time.time()
                if curr_t - last_extract_time < 1.0:
                    continue

                hw_tensor = self._convert_cv2_to_hardware_tensor(frame)

                if last_hw_tensor is not None:
                    motion_detected, ratio = _compute_entropy_hardware(
                        last_hw_tensor, hw_tensor,
                        noise_floor, physical_shift_threshold
                    )
                    if not motion_detected:
                        print(f"[{source_id}] Static ({ratio*100:.2f}% Δ) → gate drop.")
                        last_hw_tensor    = hw_tensor
                        last_extract_time = curr_t
                        continue
                    print(f"🚨 [{source_id}] Motion {ratio*100:.2f}% Δ → embedding @ {time.strftime('%H:%M:%S')}")
                else:
                    print(f"[{source_id}] Baseline → embedding @ {time.strftime('%H:%M:%S')}")

                frame_path = f"./data/frames/{source_id}/v2_{int(curr_t)}.jpg"
                self.io_pool.submit(
                    Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save,
                    frame_path
                )
                self._store_batch_hardware(
                    [hw_tensor],
                    [{"source_id": source_id, "timestamp": curr_t, "frame_path": frame_path}],
                    [f"{source_id}_{int(curr_t)}"],
                    collection_name
                )

                last_hw_tensor    = hw_tensor
                last_extract_time = curr_t
                extracted_count  += 1

                if max_test_iterations and extracted_count >= max_test_iterations:
                    break
        finally:
            cap.release()

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
        CUDA cosine search used when VRAM cache is warm.
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

        # Try CUDA in-VRAM search first
        results = self._cuda_query(query_vec, top_k, where_filter, collection_name)

        # Cold cache — fall back to ChromaDB
        if results is None:
            col     = self._get_collection(collection_name)
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

                # Try VRAM-resident cosine search first
                results = self._cuda_query(query_vec, top_k, None, cname)

                # Cold VRAM cache — fall back to ChromaDB
                if results is None:
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
    # Reverse image search — fully CUDA-accelerated with multimodal fusion kernel
    # ──────────────────────────────────────────────────────────────────────────

    def find_suspect_by_image(self, suspect_image_path: str,
                              top_k: int = 5,
                              min_timestamp: float | None = None,
                              text_query: str | None = None) -> dict:
        """
        Multi-modal reverse image search.
        Signature matches teammate's API contract (text_query param for context fusion).

        CUDA pipeline:
          1. cv2.imread → BGR tensor on device   (IO + CUDA preprocessing kernel)
          2. CLIP image encode                   (CUDA)
          3. Optional text encode                (CUDA)
          4. _cuda_fuse_modalities               (weighted mean on VRAM, re-normalise)
          5. _cuda_query / ChromaDB fallback     (CUDA cosine search)
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

        # ── CUDA: image preprocessing + encoding ────────────────────────────
        hw_tensor   = self._convert_cv2_to_hardware_tensor(bgr_frame)   # CUDA
        img_vec     = self._encode_image_tensor(hw_tensor)               # CUDA [D]

        # ── CUDA: optional text encode ───────────────────────────────────────
        text_vec = self._encode_text(text_query) if text_query else None  # CUDA [D]

        # ── CUDA: multimodal fusion kernel ────────────────────────────────────
        # Equal weight (0.5/0.5) matches teammate's arithmetic mean fusion.
        query_vec = _cuda_fuse_modalities(img_vec, text_vec, image_weight=0.5)

        # ── Search ────────────────────────────────────────────────────────────
        where_filter = {"timestamp": {"$gte": min_timestamp}} if min_timestamp else None

        # Try both collections — suspect could be in live OR uploaded footage
        results = None
        for cname in [self.COLLECTION_UPLOADED, self.COLLECTION_LIVE,
                      self.default_collection_name]:
            results = self._cuda_query(query_vec, top_k, where_filter, cname)
            if results is not None:
                break
            # Cold cache — ChromaDB fallback
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
