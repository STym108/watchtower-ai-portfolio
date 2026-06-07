"""
model/vectordb.py — Vector Database Manager Module
==================================================
This module wraps ChromaDB, our persistent vector database.
It is responsible for creating, initializing, and maintaining collections (tables),
adding batches of embeddings with metadata, and performing cosine similarity searches.

Coordination:
- Used by: model/pipelineY.py (to save processed frame vectors and search for query matches).
"""

import os
import chromadb

class VectorDBManager:
    """
    Manages collection lifecycles, vector insertions, and similarity search queries in ChromaDB.
    
    Why ChromaDB:
      It provides a lightweight, serverless vector database that persists to local disk.
      By indexing CLIP embeddings, we can find frames matching text or image queries 
      in milliseconds, even with thousands of video frames.
    """
    def __init__(self, default_collection: str, additional_collections: list[str]):
        # Ensure database storage directory exists
        db_path = "./data/vector_db"
        os.makedirs(db_path, exist_ok=True)
        
        # Connect to ChromaDB using persistent disk storage
        self.client = chromadb.PersistentClient(path=db_path)
        self.default_collection = default_collection
        
        # Set up collections in cosine similarity space (hnsw:space = cosine).
        # This is critical for CLIP embeddings, where similarity is measured by vector angle.
        all_collections = set([default_collection] + additional_collections)
        for name in all_collections:
            self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}
            )

    def get_collection(self, name: str):
        """
        Retrieves a collection object, creating it if it doesn't already exist.
        """
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )

    def delete_source_data(self, collection_name: str, source_id: str):
        """
        Deletes all vector database entries associated with a specific video file (source_id).
        This matches the 'fresh-start' requirement when re-uploading a video with the same name.
        """
        try:
            col = self.get_collection(collection_name)
            col.delete(where={"source_id": source_id})
            print(f"🧹 [VectorDB] Purged previous entries for '{source_id}' in [{collection_name}]")
        except Exception as e:
            # If the database or collection has no items yet, ignore the error
            print(f"⚠️ [VectorDB] Clean up warning for '{source_id}' in [{collection_name}]: {e}")

    def add_embeddings(self, collection_name: str, embeddings: list, metadatas: list, ids: list):
        """
        Inserts a batch of frame embeddings along with metadata (source_id, timestamp, frame_path)
        and custom string IDs.
        """
        col = self.get_collection(collection_name)
        col.add(
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        print(f"💾 [VectorDB] Stored {len(embeddings)} frames → [{collection_name}] (Total collection size: {col.count()})")

    def query(self, collection_name: str, query_embedding: list, top_k: int, where_filter: dict | None = None) -> dict:
        """
        Queries a ChromaDB collection using a query embedding.
        
        Parameters:
          - collection_name: Collection to search.
          - query_embedding: The 1D CLIP vector to match against.
          - top_k: Number of nearest matches to return.
          - where_filter: Optional ChromaDB metadata filter (e.g. filter by source_id or timestamp).

        Returns:
          - A dictionary containing lists of matching ids, metadatas, and distances.
        """
        col = self.get_collection(collection_name)
        
        # Return empty result structure if collection is empty to prevent queries on zero elements
        if col.count() == 0:
            return {"ids": [], "metadatas": [], "distances": []}

        # ChromaDB query will return the closest items based on cosine distance.
        # cosine distance = 1.0 - cosine similarity (so smaller distances mean closer matches).
        return col.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, col.count()),
            where=where_filter,
            include=["metadatas", "distances", "documents"]
        )

    def find_matching_frames(self, collection_name: str, query_emb: list, top_k: int, min_timestamp: float | None = None, source_id: str | None = None) -> list[dict]:
        """
        Queries a specific collection and filters out any matches whose frame images no longer exist on disk.
        """
        where_filter: dict = {}
        if min_timestamp is not None:
            where_filter["timestamp"] = {"$gte": min_timestamp}
        if source_id is not None:
            where_filter["source_id"] = source_id
        
        results = self.query(
            collection_name=collection_name,
            query_embedding=query_emb,
            top_k=top_k,
            where_filter=where_filter if where_filter else None
        )
        if not results.get('ids') or not results['ids'][0]:
            return []
        
        # Verify that match image files exist on disk
        valid = []
        for m in results['metadatas'][0]:
            if os.path.exists(m['frame_path']):
                valid.append(m)
        return valid

    def find_suspect_frames(self, query_emb: list, top_k: int, min_timestamp: float | None = None) -> list[dict]:
        """
        Searches all available collections (uploaded, live, and default) for suspect matches,
        filtering by distance and checking file existence on disk.
        """
        where_filter = {"timestamp": {"$gte": min_timestamp}} if min_timestamp else None
        results = None
        
        # Try both collections and fallback
        for cname in ["uploaded_vault", "live_cctv_stream", self.default_collection]:
            r = self.query(cname, query_emb, top_k, where_filter)
            if r.get('ids') and r['ids'][0]:
                results = r
                break
        
        if results is None or not results.get('ids') or not results['ids'][0]:
            return []
            
        metadatas = results['metadatas'][0]
        distances = results.get('distances', [[0.0] * len(metadatas)])[0]
        
        valid = []
        for m, d in zip(metadatas, distances):
            if os.path.exists(m['frame_path']):
                valid.append({
                    "source_id": m["source_id"],
                    "timestamp": m["timestamp"],
                    "frame_path": m["frame_path"],
                    "distance": d
                })
        return valid

    def build_trajectory(self, query_emb: list, top_k: int, max_distance: float) -> list[dict]:
        """
        Queries all collections, filters by maximum distance threshold,
        deduplicates frames, sorts chronologically, and groups matches
        into timeline events (same camera, gap <= 60 seconds).
        """
        collections_to_search = ["uploaded_vault", "live_cctv_stream", self.default_collection]
        all_metadatas = []
        all_distances = []
        
        for cname in collections_to_search:
            try:
                results = self.query(cname, query_emb, top_k)
                if results and results.get("ids") and results["ids"][0]:
                    batch_meta = results["metadatas"][0]
                    batch_dist = results.get("distances", [[0.0] * len(batch_meta)])[0]
                    all_metadatas.extend(batch_meta)
                    all_distances.extend(batch_dist)
            except Exception as e:
                print(f"⚠️ [VectorDB] Search error in '{cname}': {e}")
                
        if not all_metadatas:
            return []
            
        # Filter by distance limit and check files on disk
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
            return []
            
        # Deduplicate matching frames by path
        seen = set()
        deduped = []
        for f in valid_frames:
            if f["frame_path"] not in seen:
                seen.add(f["frame_path"])
                deduped.append(f)
        valid_frames = deduped
        
        # Sort chronologically
        valid_frames.sort(key=lambda x: x["timestamp"])
        
        # Compress frames into continuous time blocks
        timeline = []
        current_block = None
        
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
            
        return timeline

