import cv2
import torch
import os
import shutil

# FIX: Allow OpenCV/FFmpeg to connect to local IP cameras using self-signed HTTPS certificates
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "tls_verify;0"
import chromadb
from PIL import Image
import open_clip
from google import genai
import concurrent.futures
import queue
import threading
import uuid

class OfflineVideoPipeline:
    def __init__(self, api_key, collection_name="cctv_main_stream"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.model, _, self.preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
        self.model = self.model.to(self.device)
        self.tokenizer = open_clip.get_tokenizer('ViT-B-32')
        
        self.chroma_client = chromadb.PersistentClient(path="./data/vector_db")
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)
        
        self.vlm_client = genai.Client(api_key=api_key)
        self.vlm_model_name = "gemini-2.5-flash" # Use stable flash model for 1500 RPM quota
        self.io_pool = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        
        self.ai_queue = queue.Queue(maxsize=128)
        self.worker_thread = threading.Thread(target=self._ai_worker, daemon=True)
        self.worker_thread.start()

    def _ai_worker(self):
        """ Background thread that crunches numbers cleanly separating streams and uploaded videos. """
        batches = {} # Use dicts to isolate frames by collection_name

        while True:
            try:
                task = self.ai_queue.get()
                if task is None: break 

                # --- FLUSH SIGNAL HANDLING ---
                if isinstance(task, tuple) and len(task) >= 4 and task[0] == "FLUSH":
                    source_id = task[1]
                    collection_name = task[2]

                    if collection_name in batches and batches[collection_name]["images"]:
                        b = batches[collection_name]
                        print(f"✅ [AI Worker] Flushing final batch ({len(b['images'])} frames) for {source_id} in {collection_name}")
                        self._store_batch(b["images"], b["metadatas"], b["ids"], collection_name)
                        # Reset
                        batches[collection_name] = {"images": [], "metadatas": [], "ids": []}
                    continue

                pil_img, metadata, source_id, timestamp, collection_name = task

                # Initialize batch dictionary if missing for this specific context
                if collection_name not in batches:
                    batches[collection_name] = {"images": [], "metadatas": [], "ids": []}

                b = batches[collection_name]
                b["images"].append(pil_img)
                b["metadatas"].append(metadata)
                b["ids"].append(f"{source_id}_{timestamp:.2f}")

                if len(b["images"]) >= 32: 
                    self._store_batch(b["images"], b["metadatas"], b["ids"], collection_name)
                    batches[collection_name] = {"images": [], "metadatas": [], "ids": []}

            except Exception as e:
                print(f"❌ [AI Worker] ERROR: {e}")
            finally:
                self.ai_queue.task_done()
    def ingest_video(self, video_path, source_id, collection_name="cctv_main_stream", fps_to_extract=1, batch_size=64, on_frame=None):
        """Extracts frames, gets embeddings, and saves to VectorDB."""
        frames_dir = f"./data/frames/{source_id}"
        if os.path.exists(frames_dir):
            print(f"🧹 [Fresh Start] Cleaning out old frames in: {frames_dir}")
            shutil.rmtree(frames_dir)
        os.makedirs(frames_dir, exist_ok=True)

        try:
            print(f"🧹 [Fresh Start] Purging old VectorDB metadata for {source_id} in {collection_name}")
            col = self.chroma_client.get_or_create_collection(name=collection_name)
            col.delete(where={"source_id": source_id})
        except Exception as e:
            pass

        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"❌ [ML Engine] ERROR: Could not open video source: {video_path}")
            return
            
        print(f"✅ [ML Engine] Successfully connected to source: {source_id}")
        fps = round(cap.get(cv2.CAP_PROP_FPS))
        if fps <= 0: fps = 25 
        frame_interval = max(1, int(fps / fps_to_extract))
        
        count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break
            
            if on_frame:
                on_frame(frame)
            
            if count % frame_interval == 0:
                timestamp = count / fps
                frame_path = f"./data/frames/{source_id}/t_{timestamp:.1f}.jpg"
                metadata = {"source_id": source_id, "timestamp": timestamp, "frame_path": frame_path}
                
                try:
                    # --- CRITICAL FIX: Save frame SYNCHRONOUSLY to ensure disk exists ---
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(rgb_frame)
                    pil_img.save(frame_path)
                    
                    # Push PIL image to background worker for CLIP analysis
                    self.ai_queue.put_nowait((pil_img, metadata, source_id, timestamp, collection_name))
                except Exception as e:
                    print(f"⚠️ [Ingestion] Skipped frame for {source_id}: {e}")
                
            count += 1
        cap.release()
        
        print(f"🏁 [ML Engine] Ingestion finished reading for {source_id}. Waiting for AI Worker...")
        self.ai_queue.put(("FLUSH", source_id, collection_name, True))
        self.ai_queue.join()
        print(f"✅ [ML Engine] AI processing completed for {source_id}.")

    def _store_batch(self, images, metadatas, ids, collection_name):
        tensors = torch.stack([self.preprocess(img) for img in images]).to(self.device)
        with torch.no_grad():
            features = self.model.encode_image(tensors)
            features /= features.norm(dim=-1, keepdim=True)
            
        col = self.chroma_client.get_or_create_collection(name=collection_name)
        col.add(embeddings=features.cpu().tolist(), metadatas=metadatas, ids=ids)
        print(f"💾 [ML Engine] Successfully stored batch of {len(images)} frames in {collection_name}. Total count: {col.count()}")

    def query(self, text_query, top_k=5, source_id=None, collection_name=None, is_stream=False):
        if collection_name is None:
            collection_name = "live_cctv_stream" if is_stream else "uploaded_vault"

    def find_suspect_by_image(self, suspect_image_path, top_k=5, min_timestamp=None, text_query=None):
        """
        Multi-Modal Reverse Image Search Kernel!
        Fuses visual identity from a mugshot with a text-based context (e.g. 'carrying a bag').
        """
        print(f"\n[FACIAL/OBJECT RECOGNITION] Fusing visual mugshot with text context: '{text_query}'")
        
        pil_img = Image.open(suspect_image_path).convert("RGB")
        img_tensor = self.preprocess(pil_img).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            # 👁️ Step 1: Encode the Visual Mugshot
            img_features = self.model.encode_image(img_tensor)
            img_features /= img_features.norm(dim=-1, keepdim=True)

            # ✍️ Step 2: Encode the Text Context (if provided)
            if text_query:
                text_input = self.tokenizer([text_query]).to(self.device)
                text_features = self.model.encode_text(text_input)
                text_features /= text_features.norm(dim=-1, keepdim=True)
                
                # 🧬 FUSION: Mean Average of Image and Text Vectors
                # This finds the "Sweet Spot" where BOTH conditions are true.
                query_features = (img_features + text_features) / 2
                query_features /= query_features.norm(dim=-1, keepdim=True)
            else:
                query_features = img_features

        where_filter = None
        if min_timestamp is not None:
            where_filter = {"timestamp": {"$gte": min_timestamp}}

        results = self.collection.query(
            query_embeddings=[query_features.cpu().tolist()[0]], 
            n_results=top_k,
            where=where_filter 
        )
        
        if not results['ids'] or not results['ids'][0]:
            return {"status": "error", "message": "Suspect/Object not found in surveillance footage."}

        # Filter for frame existence on disk
        metadatas = results['metadatas'][0]
        distances = results['distances'][0]
        valid_frames = []
        
        for m, dist in zip(metadatas, distances):
            if os.path.exists(m['frame_path']):
                valid_frames.append({
                    "source_id": m["source_id"],
                    "timestamp": m["timestamp"],
                    "frame_path": m["frame_path"],
                    "distance": dist
                })
        
        if not valid_frames:
            return {"status": "error", "message": "No valid image frames found on disk for this suspect photo."}

        # 🤖 Stage 2: Detailed VLM Reasoning
        vlm_content =[
            f"You are a strict security facial recognition and object-matching AI Agent.",
            f"Result: A suspect image/action has been matched to CCTV footage.",
            f"User Context: {text_query if text_query else 'General identification ONLY.'}",
            "Analyze the CCTV frames compared to the search subject for a positive match and action confirmation.",
            "Be highly concise. State MATCH CONFIRMED or NO MATCH, followed by a professional response."
        ]
        
        for m in valid_frames[:3]: 
            vlm_content.append(Image.open(m['frame_path']))

        try:
            response = self.vlm_client.models.generate_content(model=self.vlm_model_name, contents=vlm_content)
            vlm_report = response.text
        except Exception as e:
            print(f"⚠️ VLM Reasoning Error: {e}")
            vlm_report = f"AI reasoning is temporarily offline due to API limits. Visual search confirmed {len(valid_frames)} matching occurrences."
        
        return {
            "status": "success",
            "query": f"Mugshot + {text_query if text_query else 'Visual Only'}",
            "response": vlm_report,
            "source_id": valid_frames[0]['source_id'],
            "clip_start": max(0, min([f['timestamp'] for f in valid_frames]) - 2.0),
            "clip_end": max([f['timestamp'] for f in valid_frames]) + 2.0,
            "frame_path": valid_frames[0]['frame_path'],
            "all_matches": valid_frames
        }

    def query(self, text_query, top_k=5, min_timestamp=None, source_id=None, is_stream=False, collection_name=None):
        """Searches the VectorDB and asks the VLM to verify."""
        if collection_name is None:
            collection_name = "live_cctv_stream" if is_stream else "uploaded_vault"
            
        text_input = self.tokenizer([text_query]).to(self.device)
        with torch.no_grad():
            features = self.model.encode_text(text_input)
            features /= features.norm(dim=-1, keepdim=True)
            
        # adding a filter by time and source
        where_filter = {}
        if min_timestamp is not None:
            where_filter["timestamp"] = {"$gte": min_timestamp}
        if source_id is not None:
            where_filter["source_id"] = source_id
            
        if not where_filter:
            where_filter = None

        col = self.chroma_client.get_or_create_collection(name=collection_name)
        results = col.query(
            query_embeddings=[features.cpu().tolist()[0]], 
            n_results=top_k,
            where=where_filter 
        )
        
        if not results['ids'] or not results['ids'][0]:
            return {"status": "error", "message": "No matches found."}

        raw_frames = results['metadatas'][0]
        valid_frames = []
        vlm_content =[f"Query: '{text_query}'. You are a Quick Search Assistant. Analyze these frames and confirm if the target is present. Provide a professional 2-line summary of what you see. Mention the primary frame of detection clearly."]

        for m in raw_frames: 
            if os.path.exists(m['frame_path']):
                valid_frames.append(m)
                vlm_content.append(Image.open(m['frame_path']))
            else:
                print(f"  -> Ignoring stale metadata (file missing): {m['frame_path']}")
        
        if not valid_frames:
            return {"status": "error", "message": "No valid image frames found on disk for this query."}
        
        if len(vlm_content) <= 1:
            return {"status": "error", "message": "No valid image frames found on disk."}

        response = self.vlm_client.models.generate_content(model=self.vlm_model_name, contents=vlm_content)
        
        valid_timestamps = [m['timestamp'] for m in valid_frames]
        return {
            "query": text_query,
            "response": response.text,
            "source_id": valid_frames[0]['source_id'],
            "clip_start": max(0, min(valid_timestamps) - 2.0),
            "clip_end": max(valid_timestamps) + 2.0,
            "frame_path": valid_frames[0]['frame_path'],
            "all_matches": valid_frames
        }

    def track_timeline(self, text_query, top_k=20, max_distance=2.0):
        """
        Detective Mode: Maps an object's complete chronological 
        history across all ingested video feeds and compresses it into a Timeline.
        """
        # CLEANING: If the query is conversational, we should ideally simplify it.
        # For now, we will simply use a very high sensitivity (2.0) and let the VLM verify.
        print(f"\n[TRACING] Investigating lineage for: '{text_query}'")
        text_input = self.tokenizer([text_query]).to(self.device)
        with torch.no_grad():
            features = self.model.encode_text(text_input)
            features /= features.norm(dim=-1, keepdim=True)
            
        results = self.collection.query(
            query_embeddings=[features.cpu().tolist()[0]], 
            n_results=top_k,
            include=['metadatas', 'distances'] 
        )
        
        if not results['ids'] or not results['ids'][0]:
            return {"status": "error", "message": "Target not detected anywhere."}

        metadatas = results['metadatas'][0]
        distances = results['distances'][0]
        
        # SAFETY FIRST: Filter for both distance AND file existence!
        valid_found = []
        for meta, dist in zip(metadatas, distances):
            if dist <= max_distance:
                if os.path.exists(meta['frame_path']):
                    valid_found.append({
                        "source_id": meta["source_id"],
                        "timestamp": meta["timestamp"],
                        "frame_path": meta["frame_path"],
                        "distance": dist
                    })
                else:
                    print(f"  -> Skipping timeline ghost: {meta['frame_path']}")

        if not valid_found:
            return {"status": "error", "message": "No confident/existing target locks achieved."}

        valid_found.sort(key=lambda x: x["timestamp"])

        timeline = []
        current_block = None

        for frame in valid_found:
            if current_block is None:
                current_block = {
                    "source_id": frame["source_id"], 
                    "start_time": frame["timestamp"], 
                    "end_time": frame["timestamp"], 
                    "best_frame": frame["frame_path"]
                }
                continue
                
            time_gap = frame["timestamp"] - current_block["end_time"]
            if frame["source_id"] == current_block["source_id"] and time_gap <= 60.0:
                current_block["end_time"] = frame["timestamp"]
            else:
                timeline.append(current_block)
                current_block = {
                    "source_id": frame["source_id"], 
                    "start_time": frame["timestamp"], 
                    "end_time": frame["timestamp"], 
                    "best_frame": frame["frame_path"]
                }
        if current_block: timeline.append(current_block)

        vlm_content =[
            f"You are a master Surveillance Intelligence Agent specializing in cross-camera lineage tracking.",
            f"User request: '{text_query}'.",
            "You have been provided with chronological photographic evidence of the target across multiple camera feeds.",
            "Analyze every frame deeply. Synthesize a professional, highly detailed incident timeline detailing where they went, what they were doing, and their visible behavior across these zones. Be descriptive and act like a lead detective."
        ]
        
        for idx, block in enumerate(timeline):
            vlm_content.append(f"Incident Event {idx+1} at camera: {block['source_id']}")
            vlm_content.append(Image.open(block['best_frame']))
            
        vlm_content.append(
            "Synthesize a strict, professional incident timeline detailing "
            "where they went and what they were doing across these zones."
        )

        response = self.vlm_client.models.generate_content(model=self.vlm_model_name, contents=vlm_content)

        return {
            "status": "success",
            "target": text_query,
            "incident_report": response.text,
            "timeline_nodes": timeline 
        }
