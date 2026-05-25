#include <torch/extension.h>
#include <cmath>

#ifdef WITH_CUDA
// CUDA forward declarations (from entropy_gate_cuda.cu)
torch::Tensor cuda_compute_entropy_mask(torch::Tensor prev, torch::Tensor curr, float noise_ceil);
torch::Tensor cuda_topk_cosine(torch::Tensor query_vec, torch::Tensor candidate_vecs, int64_t top_k);
torch::Tensor cuda_fuse_modalities(torch::Tensor image_vec, torch::Tensor text_vec, float image_weight);
#endif

// 1. Motion Entropy Gate (CPU Fallback + CUDA routing)
bool compute_entropy(torch::Tensor prev, torch::Tensor curr, float noise_ceil, float shift_threshold) {
#ifdef WITH_CUDA
    if (prev.is_cuda()) {
        auto mask = cuda_compute_entropy_mask(prev, curr, noise_ceil);
        float ratio = mask.mean().item<float>();
        return ratio >= shift_threshold;
    }
#endif

    // OpenMP CPU Fallback
    int n = prev.numel();
    const float* p_data = prev.data_ptr<float>();
    const float* c_data = curr.data_ptr<float>();
    
    int changed = 0;
    #pragma omp parallel for reduction(+:changed)
    for (int i = 0; i < n; i++) {
        float diff = std::abs(c_data[i] - p_data[i]);
        if (diff > noise_ceil) {
            changed += 1;
        }
    }
    
    float ratio = static_cast<float>(changed) / n;
    return ratio >= shift_threshold;
}

// 2. Top-K Cosine Search (CPU Fallback + CUDA routing)
torch::Tensor topk_cosine_search(torch::Tensor query_vec, torch::Tensor candidate_vecs, int64_t top_k) {
#ifdef WITH_CUDA
    if (query_vec.is_cuda()) {
        return cuda_topk_cosine(query_vec, candidate_vecs, top_k);
    }
#endif

    // ATen CPU/MPS Fallback
    auto sims = torch::matmul(candidate_vecs, query_vec);
    int64_t k = std::min(top_k, (int64_t)sims.size(0));
    return std::get<1>(torch::topk(sims, k));
}

// 3. Modality Fusion (CPU Fallback + CUDA routing)
torch::Tensor fuse_modalities(torch::Tensor image_vec, torch::Tensor text_vec, float image_weight) {
#ifdef WITH_CUDA
    if (image_vec.is_cuda()) {
        return cuda_fuse_modalities(image_vec, text_vec, image_weight);
    }
#endif

    // ATen CPU/MPS Fallback
    torch::NoGradGuard no_grad;
    auto fused = image_weight * image_vec + (1.0f - image_weight) * text_vec;
    fused = fused / fused.norm(2, -1, true);
    return fused;
}

// PyBind11 Module Definition
PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("compute_entropy", &compute_entropy, "Compute motion entropy");
    m.def("topk_cosine_search", &topk_cosine_search, "Top-K cosine similarity search");
    m.def("fuse_modalities", &fuse_modalities, "Fuse image and text vectors");
}
