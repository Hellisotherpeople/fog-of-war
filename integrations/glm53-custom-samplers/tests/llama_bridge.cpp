// Test-only adapter to the actual compiled llama.cpp DRY implementation.
#include "llama.h"
#include <vector>
extern llama_sampler * llama_sampler_init_dry_testing(float, float, int32_t, int32_t,
    const std::vector<std::vector<llama_token>> &);
extern "C" llama_sampler * test_dry_init(float multiplier, float base, int allowed,
    int last_n, const int * tokens, const int * sizes, int count) {
    std::vector<std::vector<llama_token>> sequences;
    for (int i = 0; i < count; ++i) {
        sequences.emplace_back(tokens, tokens + sizes[i]);
        tokens += sizes[i];
    }
    return llama_sampler_init_dry_testing(multiplier, base, allowed, last_n, sequences);
}
