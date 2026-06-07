"""
model/embedder.py — Hardware-Accelerated Vector Embeddings Module
================================================================
This module handles all operations related to machine learning feature extraction.
It initializes open-source CLIP models on the fastest available hardware (CUDA/MPS/CPU),
handles image preprocessing via PyTorch tensors, generates embeddings for images and text,
and performs multimodal vector fusion.

Coordination:
- Used by: model/pipelineY.py (for processing incoming video frames and search queries).
"""

import torch
import torchvision.transforms.v2 as T
import open_clip

def fuse_modalities(image_vec: torch.Tensor,
                    text_vec: torch.Tensor | None,
                    image_weight: float = 0.5) -> torch.Tensor:
    """
    Combines visual features and text query context into a single multimodal vector.
    
    Why we use this:
      During reverse image search, the user might search for an image *and* provide
      additional text context (e.g. searching a photo of a person + text 'backpack').
      We fuse these vectors mathematically so that both visual and textual features
      influence the database search.

    Parameters:
      - image_vec: Normalized PyTorch tensor representing visual features.
      - text_vec: Optional normalized PyTorch tensor representing textual features.
      - image_weight: How much weight to give the visual features (defaults to 0.5/0.5 equal fusion).

    Returns:
      - A normalized fused vector.
    """
    if text_vec is None:
        return image_vec
    
    with torch.no_grad():
        # Weighted linear combination of the two vectors
        fused = image_weight * image_vec + (1.0 - image_weight) * text_vec
        # Re-normalize to unit length (L2 norm) so cosine similarity queries work correctly
        fused /= fused.norm(dim=-1, keepdim=True)
    return fused


class Embedder:
    """
    Manages loading the CLIP model and running hardware-accelerated feature extraction.
    
    Features:
      - Automatic hardware selection (NVIDIA CUDA, Apple Silicon MPS, or CPU fallback).
      - Thread-safe, evaluation-mode model operations (`eval()`).
      - Batch image encoding for maximum throughput during video ingestion.
    """
    def __init__(self):
        # 1. Automatic hardware discovery for best performance
        if torch.cuda.is_available():
            self.device = "cuda"
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        print(f"\n🧠 [Embedder] Hardware locked → [{self.device.upper()}]")
        if self.device == "cuda":
            props = torch.cuda.get_device_properties(0)
            print(f"   GPU Model: {props.name} | VRAM: {props.total_memory // 1024**2} MB")

        # 2. Load open-source CLIP model (Vision Transformer ViT-B-32)
        # Pretrained on OpenAI dataset for highly accurate zero-shot image-text matching.
        self.model, _, _ = open_clip.create_model_and_transforms(
            'ViT-B-32', pretrained='openai'     
        )
        self.model = self.model.to(self.device).eval()  # Set model to evaluation mode
        self.tokenizer = open_clip.get_tokenizer('ViT-B-32')

        # 3. Define device-side image preprocessing pipeline
        # Normalization values match CLIP's original training configuration.
        self.device_preprocess = T.Compose([
            T.Resize(224, antialias=True),
            T.CenterCrop(224),
            T.Normalize(
                mean=(0.48145466, 0.4578275,  0.40821073),
                std= (0.26862954, 0.26130258, 0.27577711)
            )
        ])

    def convert_frame_to_tensor(self, frame_bgr) -> torch.Tensor:
        """
        Converts an OpenCV BGR numpy frame into a preprocessed PyTorch float tensor on the target device.
        
        Steps:
          1. Convert NumPy array to PyTorch tensor.
          2. Rearrange dimensions from HWC (Height, Width, Channel) to CHW.
          3. Convert color space from BGR (OpenCV default) to RGB.
          4. Normalize pixel values from [0, 255] to [0.0, 1.0].
          5. Resize, crop, and normalize using CLIP statistics.
        """
        # Load array to device memory
        hw = torch.from_numpy(frame_bgr).permute(2, 0, 1).float().to(self.device)
        # BGR -> RGB slice and range scale
        hw = hw[[2, 1, 0], ...] / 255.0
        # Crop & normalize
        return self.device_preprocess(hw)

    def encode_image_tensor(self, tensor: torch.Tensor) -> torch.Tensor:
        """
        Encodes a single preprocessed image tensor (CHW) into a normalized 1D vector.
        """
        with torch.no_grad():
            # Add batch dimension: CHW -> 1xCHW
            feat = self.model.encode_image(tensor.unsqueeze(0))
            # Normalize to unit vector for cosine distance calculations
            feat /= feat.norm(dim=-1, keepdim=True)
        return feat.squeeze(0)

    def encode_image_batch(self, tensor_list: list[torch.Tensor]) -> torch.Tensor:
        """
        Stacks multiple image tensors and encodes them in a single batch.
        This utilizes GPU/MPS parallel execution to speed up ingestion of long videos.
        """
        if not tensor_list:
            return torch.empty(0)
        
        # Stack list of shape [CHW] into a single tensor of shape [Batch, CHW]
        tensors = torch.stack(tensor_list).to(self.device)
        with torch.no_grad():
            features = self.model.encode_image(tensors)
            # Normalize each vector in the batch along the final dimension
            features /= features.norm(dim=-1, keepdim=True)
        return features

    def encode_text(self, text: str) -> torch.Tensor:
        """
        Tokenizes and encodes a text string query into a normalized 1D CLIP vector.
        """
        # Tokenize text according to CLIP's vocabulary limits
        tokens = self.tokenizer([text]).to(self.device)
        with torch.no_grad():
            feat = self.model.encode_text(tokens)
            feat /= feat.norm(dim=-1, keepdim=True)
        return feat.squeeze(0)

    def encode_image_path(self, path: str) -> torch.Tensor | None:
        """
        Loads an image file from disk, preprocesses it, and generates its normalized CLIP embedding.
        Returns None if the file cannot be read.
        """
        import cv2
        img = cv2.imread(path)
        if img is None:
            return None
        tensor = self.convert_frame_to_tensor(img)
        return self.encode_image_tensor(tensor)

