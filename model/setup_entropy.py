"""
setup_entropy.py — WatchTower.ai CUDA/OpenMP Extension Builder
==============================================================
Builds all three kernels exposed to pipelineY.py:
    1. compute_entropy       — motion entropy gate
    2. topk_cosine_search    — all-VRAM cosine similarity search
    3. fuse_modalities       — multimodal image+text vector fusion

Usage:
    python setup_entropy.py build_ext --inplace

CUDA flags:
    -arch=sm_86     Ampere (RTX 3000 series). Change to:
                    sm_89  for RTX 4000 series (Ada Lovelace)
                    sm_80  for A100
                    sm_75  for RTX 2000 series (Turing)
    --use_fast_math Enables fused multiply-add and fast reciprocal sqrt
                    Safe here — we only use fabsf, multiply, divide, sqrt.

OpenMP flags:
    -fopenmp added to both cxx and linker flags.
    Applied to CPU fallback path in entropy_gate.cpp only.
    CUDA host launcher runs single-threaded; GPU parallelism is internal.

Output:
    entropy_gate.cpython-3XX-<platform>.so   (in project root with --inplace)
"""

from torch.utils.cpp_extension import CppExtension, CUDAExtension, BuildExtension
from setuptools import setup
import torch
import os

os.makedirs("build", exist_ok=True)

if torch.cuda.is_available():
    # ── CUDA + OpenMP build ───────────────────────────────────────────────────
    # Detect GPU compute capability for better default (optional override below)
    cc_major, cc_minor = torch.cuda.get_device_capability(0)
    arch = f"sm_{cc_major}{cc_minor}"
    print(f"Detected GPU compute capability: {arch}")

    # Allow manual override via environment variable
    # e.g.:  SM_ARCH=sm_89 python setup_entropy.py build_ext --inplace
    arch = os.environ.get("SM_ARCH", arch)
    print(f"Building with CUDA support ({arch}) + OpenMP CPU fallback.")

    ext = CUDAExtension(
        name="entropy_gate",
        sources=["entropy_gate.cpp", "entropy_gate_cuda.cu"],
        extra_compile_args={
            "cxx":  [
                "-O3",
                "-fopenmp",              # OpenMP for CPU abs loop in entropy gate
                "-std=c++17",
            ],
            "nvcc": [
                "-O3",
                f"-arch={arch}",         # Ampere sm_86 for RTX 3000
                "--use_fast_math",       # safe: fabsf, fma, fast reciprocal sqrt
                "-std=c++17",
                # Suppress verbose deprecation warnings from torch headers
                "-Xcudafe", "--diag_suppress=20012",
            ],
        },
        extra_link_args=["-fopenmp"],
        define_macros=[("WITH_CUDA", None)],
    )

else:
    # ── CPU / MPS only build ──────────────────────────────────────────────────
    print("No CUDA detected. Building CPU/MPS-only extension with OpenMP.")
    ext = CppExtension(
        name="entropy_gate",
        sources=["entropy_gate.cpp"],
        extra_compile_args={
            "cxx": ["-O3", "-fopenmp", "-std=c++17"]
        },
        extra_link_args=["-fopenmp"],
    )

setup(
    name="entropy_gate",
    ext_modules=[ext],
    cmdclass={"build_ext": BuildExtension},
)
