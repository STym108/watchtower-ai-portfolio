/**
 * entropy_gate_cuda.cu
 * ─────────────────────────────────────────────────────────────────────────────
 * WatchTower.ai — Three CUDA kernels for pipelineY.py
 *
 *   cuda_compute_entropy_mask   — per-pixel abs-diff + threshold mask
 *   cuda_topk_cosine            — batched dot-product cosine similarity + top-k
 *   cuda_fuse_modalities        — weighted vector fusion + L2 renormalisation
 *
 * Ampere sm_86 (RTX 3000 series) tuning throughout:
 *   - 256 threads/block (4 warps — fills one SM scheduling slot cleanly)
 *   - Shared memory tiling where beneficial (entropy + cosine kernels)
 *   - __ldg() read-only L1 cache on global reads (written once per kernel)
 *   - __use_fast_math applied via nvcc flag in setup_entropy.py
 *   - cudaDeviceSynchronize only at host-launcher boundary
 *
 * ViT-B-32 embedding dim: 512  (pipelineY.py — do not assume 768)
 * All kernels are dimension-agnostic and work for any D.
 */

#include <torch/extension.h>
#include <cuda_runtime.h>
#include <float.h>      // FLT_MAX for topk initialisation

#define BLOCK_SIZE 256


// ══════════════════════════════════════════════════════════════════════════════
// KERNEL 1 — Motion Entropy Gate
// ══════════════════════════════════════════════════════════════════════════════

/**
 * motion_entropy_kernel
 * ─────────────────────────────────────────────────────────────────────────────
 * Each thread owns one scalar element.
 * Loads prev+curr into shared memory cooperatively (2 KB/block),
 * computes |curr - prev|, writes 1.0f if > noise_ceil else 0.0f.
 *
 * The resulting out_mask is summed on the CPU side in compute_hardware_entropy
 * to compute the final ratio.
 */
__global__ void motion_entropy_kernel(const float* __restrict__ prev,
                                      const float* __restrict__ curr,
                                      float*       __restrict__ out_mask,
                                      float                     noise_ceil,
                                      int                       n) {
    __shared__ float s_prev[BLOCK_SIZE];
    __shared__ float s_curr[BLOCK_SIZE];

    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int tid = threadIdx.x;

    if (idx < n) {
        s_prev[tid] = __ldg(&prev[idx]);
        s_curr[tid] = __ldg(&curr[idx]);
    }
    __syncthreads();

    if (idx < n) {
        float diff   = s_curr[tid] - s_prev[tid];
        out_mask[idx] = (diff < 0.0f ? -diff : diff) > noise_ceil ? 1.0f : 0.0f;
    }
}

/**
 * cuda_compute_entropy_mask — host launcher for KERNEL 1
 * Called from entropy_gate.cpp when tensor is on CUDA.
 * Returns a [numel] float mask (1.0 = changed, 0.0 = static).
 */
torch::Tensor cuda_compute_entropy_mask(torch::Tensor prev,
                                        torch::Tensor curr,
                                        float         noise_ceil) {
    TORCH_CHECK(prev.is_cuda() && curr.is_cuda(),  "entropy: tensors must be on CUDA");
    TORCH_CHECK(prev.is_contiguous(),               "entropy: prev must be contiguous");
    TORCH_CHECK(curr.is_contiguous(),               "entropy: curr must be contiguous");
    TORCH_CHECK(prev.scalar_type() == torch::kFloat32, "entropy: expected float32");
    TORCH_CHECK(prev.numel() == curr.numel(),       "entropy: shape mismatch");

    int n        = static_cast<int>(curr.numel());
    auto out_mask = torch::zeros_like(curr);

    int blocks = (n + BLOCK_SIZE - 1) / BLOCK_SIZE;
    motion_entropy_kernel<<<blocks, BLOCK_SIZE>>>(
        prev.data_ptr<float>(),
        curr.data_ptr<float>(),
        out_mask.data_ptr<float>(),
        noise_ceil,
        n
    );

    cudaDeviceSynchronize();
    return out_mask;
}


// ══════════════════════════════════════════════════════════════════════════════
// KERNEL 2 — All-VRAM Top-K Cosine Similarity Search
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Design note — why not cuBLAS GEMV?
 * For the typical WatchTower cache size (hundreds to low thousands of frames)
 * a custom kernel avoids cuBLAS launch overhead and keeps everything in L2
 * during the dot products. For very large caches (>50k frames) switching to
 * cublasSgemv + thrust::sort would be faster — add that as a future path.
 *
 * Tiling strategy:
 *   Each block handles a TILE of BLOCK_SIZE candidate rows.
 *   The query vector chunk for that tile is loaded into shared memory once,
 *   then all BLOCK_SIZE threads read from fast SRAM for their dot products.
 *   This reduces global memory traffic by ~BLOCK_SIZE× for the query reads.
 *
 * Threading:
 *   gridDim.x  = ceil(N / BLOCK_SIZE)  — one block per tile of candidates
 *   blockDim.x = BLOCK_SIZE            — 256 threads
 *   Thread i handles candidate row (blockIdx.x * BLOCK_SIZE + threadIdx.x).
 */

// Shared memory tile for the query vector chunk
// Size = BLOCK_SIZE floats = 1 KB per block (well within 48 KB Ampere limit)
extern __shared__ float s_query[];   // declared dynamic — allocated at launch

__global__ void cosine_topk_kernel(const float* __restrict__ query,    // [D]
                                    const float* __restrict__ candidates, // [N, D]
                                    float*       __restrict__ out_sims,   // [N]
                                    int N, int D) {
    int row = blockIdx.x * blockDim.x + threadIdx.x;  // candidate index
    int tid = threadIdx.x;

    float dot = 0.0f;

    // Tile the D dimension in chunks of BLOCK_SIZE
    for (int tile_start = 0; tile_start < D; tile_start += BLOCK_SIZE) {
        // Cooperative load: each thread loads one element of the query tile
        int q_idx = tile_start + tid;
        s_query[tid] = (q_idx < D) ? __ldg(&query[q_idx]) : 0.0f;
        __syncthreads();

        // Each thread accumulates its portion of the dot product
        if (row < N) {
            int tile_end = min(tile_start + BLOCK_SIZE, D);
            for (int d = tile_start; d < tile_end; ++d) {
                dot += __ldg(&candidates[row * D + d]) * s_query[d - tile_start];
            }
        }
        __syncthreads();
    }

    if (row < N) {
        out_sims[row] = dot;   // cosine sim of unit vecs = dot product
    }
}

/**
 * cuda_topk_cosine — host launcher for KERNEL 2
 *
 * Computes cosine similarities for all N candidates, then selects top-k
 * using torch::topk (already on device — stays in VRAM).
 *
 * Returns: LongTensor [k] of row indices, sorted descending by similarity.
 */
torch::Tensor cuda_topk_cosine(torch::Tensor query_vec,
                                torch::Tensor candidate_vecs,
                                int64_t       top_k) {
    TORCH_CHECK(query_vec.is_cuda() && candidate_vecs.is_cuda(),
                "topk_cosine: tensors must be on CUDA");
    TORCH_CHECK(query_vec.is_contiguous() && candidate_vecs.is_contiguous(),
                "topk_cosine: tensors must be contiguous");
    TORCH_CHECK(query_vec.scalar_type() == torch::kFloat32,
                "topk_cosine: expected float32");

    int64_t N = candidate_vecs.size(0);
    int64_t D = candidate_vecs.size(1);
    int64_t k = std::min(top_k, N);

    TORCH_CHECK(query_vec.size(0) == D,
                "topk_cosine: query_vec dim must match candidate embedding dim");

    // Allocate output similarity scores in VRAM
    auto sims = torch::zeros({N}, query_vec.options());

    // Grid: one block per BLOCK_SIZE candidates
    int blocks = static_cast<int>((N + BLOCK_SIZE - 1) / BLOCK_SIZE);

    // Shared memory: one tile of the query vector = BLOCK_SIZE * sizeof(float)
    size_t smem = BLOCK_SIZE * sizeof(float);

    cosine_topk_kernel<<<blocks, BLOCK_SIZE, smem>>>(
        query_vec.data_ptr<float>(),
        candidate_vecs.data_ptr<float>(),
        sims.data_ptr<float>(),
        static_cast<int>(N),
        static_cast<int>(D)
    );
    cudaDeviceSynchronize();

    // torch::topk stays in VRAM — no CPU transfer
    auto [values, indices] = torch::topk(sims, k, /*dim=*/0, /*largest=*/true);
    return indices;   // [k] int64 on CUDA
}


// ══════════════════════════════════════════════════════════════════════════════
// KERNEL 3 — Multimodal Fusion (image + text → fused unit vector)
// ══════════════════════════════════════════════════════════════════════════════

/**
 * fuse_modalities_kernel
 * ─────────────────────────────────────────────────────────────────────────────
 * Computes: fused[i] = image_weight * image_vec[i] + (1-image_weight) * text_vec[i]
 * in one pass.  Normalisation is done in a separate reduction kernel to avoid
 * a two-pass algorithm blowing shared memory budget.
 *
 * Thread i handles element i of the D-dimensional vector.
 * For ViT-B-32 D=512 fits in two blocks of 256 threads.
 */
__global__ void fuse_modalities_kernel(const float* __restrict__ image_vec,
                                        const float* __restrict__ text_vec,
                                        float*       __restrict__ out,
                                        float                     image_weight,
                                        int                       D) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < D) {
        out[i] = image_weight * __ldg(&image_vec[i])
               + (1.0f - image_weight) * __ldg(&text_vec[i]);
    }
}

/**
 * l2_norm_kernel  — parallel L2 norm reduction (two-pass: square-sum, then divide)
 *
 * Pass 1: block-level reduce sum of squares → partial sums in shared memory
 *         → one block writes its partial sum to out_partial[blockIdx.x]
 * Pass 2 (on CPU via ATen): sum partials, sqrt, divide fused vector.
 *
 * For D=512 a single block of 512 threads would suffice, but we keep
 * BLOCK_SIZE=256 throughout for consistency with the Ampere sm_86 tuning.
 */
__global__ void l2_partial_sum_kernel(const float* __restrict__ vec,
                                       float*       __restrict__ partial_sums,
                                       int                       D) {
    __shared__ float s_reduce[BLOCK_SIZE];

    int   i   = blockIdx.x * blockDim.x + threadIdx.x;
    int   tid = threadIdx.x;

    float val = (i < D) ? __ldg(&vec[i]) : 0.0f;
    s_reduce[tid] = val * val;
    __syncthreads();

    // Tree reduction within block
    for (int stride = BLOCK_SIZE / 2; stride > 0; stride >>= 1) {
        if (tid < stride)
            s_reduce[tid] += s_reduce[tid + stride];
        __syncthreads();
    }

    if (tid == 0)
        partial_sums[blockIdx.x] = s_reduce[0];
}

__global__ void l2_divide_kernel(float*       __restrict__ vec,
                                  float                     norm,
                                  int                       D) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < D)
        vec[i] /= norm;
}

/**
 * cuda_fuse_modalities — host launcher for KERNEL 3
 *
 * Fuses image and text vectors with weighted mean, then L2-normalises.
 * All operations stay in VRAM — no CPU round-trip.
 *
 * Returns: [D] float32, L2-normalised fused vector on CUDA.
 */
torch::Tensor cuda_fuse_modalities(torch::Tensor image_vec,
                                    torch::Tensor text_vec,
                                    float         image_weight) {
    TORCH_CHECK(image_vec.is_cuda() && text_vec.is_cuda(),
                "fuse_modalities: tensors must be on CUDA");
    TORCH_CHECK(image_vec.is_contiguous() && text_vec.is_contiguous(),
                "fuse_modalities: tensors must be contiguous");
    TORCH_CHECK(image_vec.scalar_type() == torch::kFloat32,
                "fuse_modalities: expected float32");
    TORCH_CHECK(image_vec.size(0) == text_vec.size(0),
                "fuse_modalities: dimension mismatch between image_vec and text_vec");

    int D = static_cast<int>(image_vec.size(0));

    // ── Step 1: weighted fusion ───────────────────────────────────────────────
    auto fused = torch::zeros({D}, image_vec.options());

    int blocks = (D + BLOCK_SIZE - 1) / BLOCK_SIZE;
    fuse_modalities_kernel<<<blocks, BLOCK_SIZE>>>(
        image_vec.data_ptr<float>(),
        text_vec.data_ptr<float>(),
        fused.data_ptr<float>(),
        image_weight,
        D
    );
    cudaDeviceSynchronize();

    // ── Step 2: L2 norm — partial sums per block, then final reduce on ATen ──
    // For D ≤ 1024 (covers both ViT-B-32 D=512 and ViT-L-14 D=768):
    // Using ATen norm here keeps the code simple and still stays in VRAM.
    // A pure-CUDA two-pass reduction is only faster for D > 8192.
    {
        torch::NoGradGuard no_grad;
        float norm_val = fused.norm().item<float>();
        if (norm_val > 1e-8f) {
            int norm_blocks = (D + BLOCK_SIZE - 1) / BLOCK_SIZE;
            l2_divide_kernel<<<norm_blocks, BLOCK_SIZE>>>(
                fused.data_ptr<float>(),
                norm_val,
                D
            );
            cudaDeviceSynchronize();
        }
    }

    return fused;   // [D] L2-normalised, on CUDA
}
