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
