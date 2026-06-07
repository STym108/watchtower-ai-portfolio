# WatchTower: Natural Language CCTV Intelligence for Retail stores


## 🏗️ System Architecture

Our platform is divided into three core micro-architectures:

### 1. The Frontend (Client Application)
A modern, SaaS-style web application built for security operators. It features a split-screen dashboard combining a ChatGPT-like natural language interface with a Smart Video Player that dynamically scrubs to events detected by the AI.

### 2. The Backend (API Gateway & Logic)
The bridge between the user interface, the user database, and the ML engine. 
* Manages User Authentication and Profiles (Relational DB).
* Handles MP4 video uploads and static file serving.
* Manages background workers that constantly evaluate active "Alert Rules" against the latest video frames.

### 3. The ML Engine (Video-RAG Pipeline)
Located in the `/model` directory, this is a highly optimized Two-Stage Retrieval-Augmented Generation pipeline:
* **Stage 1 (Dense Retrieval):** Extracts frames from MP4 files in large batches, processes them through a Vision Encoder, and stores their mathematical representations (embeddings) in an offline **VectorDB**.
* **Stage 2 (VLM Synthesis):** When a user queries the system, it embeds the text, searches the VectorDB for the top matching visual frames, and passes the context to a Large Vision-Language Model (LVLM) to synthesize a conversational answer and confirm the event.

## 📂 Directory Structure
```text
/vision-rag
│
├── /frontend          # UI/UX codebase (Web app)
├── /backend           # API, Auth, and Routing
└── /model             # Core ML Pipeline & VectorDB
    ├── setup_env.py          # Initializes DB and folders
    ├── pipelineY.py          # The core offline ML pipeline
    └── /data                 # Shared storage (DB, Frames, Videos)
