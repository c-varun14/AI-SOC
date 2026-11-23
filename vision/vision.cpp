#include <iostream>
#include <cmath>
#include <algorithm>
#include <fstream>
#include <vector>
#include <chrono>
#include "executorch/extension/module/module.h"
#include "executorch/extension/tensor/tensor_ptr.h"

int main(int argc, char* argv[]) {
    if (argc > 2) {
        std::cerr << "Usage: " << argv[0]
                  << " [preprocessed_tensor.bin]\n";
        return 1;
    }

    const char* input_path =
        argc == 2 ? argv[1] : "test_images/pill_input.bin";

    std::cout << "PillGuard Experiment 2 Inference Test\n";

    executorch::extension::Module module(
        "pillguard_efficientnetv2_s_experiment2_xnnpack.pte"
    );

    auto status = module.load_method("forward");

    if (status != executorch::runtime::Error::Ok) {
        std::cerr << "Failed to load forward method. Error: "
                  << static_cast<int>(status) << "\n";
        return 1;
    }

    std::cout << "Forward method loaded successfully\n";

    std::vector<float> input_data(1 * 3 * 224 * 224);

    std::ifstream input_file(
        input_path,
        std::ios::binary
    );

    if (!input_file) {
        std::cerr << "Cannot open input tensor: " << input_path << "\n";
        return 1;
    }

    input_file.read(
        reinterpret_cast<char*>(input_data.data()),
        static_cast<std::streamsize>(
            input_data.size() * sizeof(float)
        )
    );

    if (input_file.gcount() !=
        static_cast<std::streamsize>(
            input_data.size() * sizeof(float)
        )) {
        std::cerr << "Invalid input tensor size\n";
        return 1;
    }

    if (input_file.peek() !=
        std::char_traits<char>::eof()) {
        std::cerr << "Input tensor has extra data\n";
        return 1;
    }

    std::cout << "Real pill image tensor loaded\n";

    auto input_tensor = executorch::extension::make_tensor_ptr(
        {1, 3, 224, 224},
        input_data.data()
    );

    if (!input_tensor) {
        std::cerr << "Failed to create input tensor\n";
        return 1;
    }

    const auto start = std::chrono::steady_clock::now();
    auto result = module.forward(
        executorch::runtime::EValue(*input_tensor)
    );
    const auto end = std::chrono::steady_clock::now();
    const double latency_ms =
        std::chrono::duration<double, std::milli>(end - start).count();

    if (!result.ok()) {
        std::cerr << "Inference failed. Error: "
                  << static_cast<int>(result.error()) << "\n";
        return 1;
    }

    if (result->size() != 1 || !result->at(0).isTensor()) {
        std::cerr << "Unexpected model output\n";
        return 1;
    }

    const auto& output = result->at(0).toTensor();

    if (output.numel() != 2) {
        std::cerr << "Unexpected output element count\n";
        return 1;
    }

    const float* scores = output.const_data_ptr<float>();

    std::cout << "Inference SUCCESS\n";
    std::cout << "Forward latency: "
              << latency_ms << " ms\n";
    std::cout << "Defective score: " << scores[0] << "\n";
    std::cout << "Normal score: " << scores[1] << "\n";


    // Convert model logits into probabilities.
    const double max_score = std::max(
        static_cast<double>(scores[0]),
        static_cast<double>(scores[1])
    );

    const double exp_defective = std::exp(scores[0] - max_score);
    const double exp_normal = std::exp(scores[1] - max_score);

    const double defective_probability =
        exp_defective / (exp_defective + exp_normal);

    const double normal_probability =
        exp_normal / (exp_defective + exp_normal);

    constexpr double DEFECTIVE_THRESHOLD = 0.30;

    const bool is_defective =
        defective_probability >= DEFECTIVE_THRESHOLD;

    std::cout << "=== PILLGUARD DEPLOYMENT RESULT ===\n";
    std::cout << "Defective probability: "
              << defective_probability << "\n";
    std::cout << "Normal probability: "
              << normal_probability << "\n";
    std::cout << "Threshold: "
              << DEFECTIVE_THRESHOLD << "\n";
    std::cout << "Prediction: "
              << (is_defective ? "DEFECTIVE" : "NORMAL")
              << "\n";
    std::cout << "Prototype screening only; not validated "
                 "for pharmaceutical quality control.\n";

    return 0;
}
