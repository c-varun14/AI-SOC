# Reproducing the Cortex-A72 Llama runner

The verified build used WSL Ubuntu, Ninja, CMake 3.28.3, Arm GNU 14.3.1 and the existing ExecuTorch Python environment for code generation. It used ExecuTorch v1.6.0 at commit `4776f71b6f0daa5dfc7d758d5836fc1cc0d40154`. The checkout directory must be named `executorch`. Initialize the pinned submodules for XNNPACK, tokenizers, Eigen, FlatBuffers, FlatCC, gflags, pocketfft, json, and torchao. The build also requires the tokenizer submodules recursively. The torchao checkout is pinned to `b7ac3aacf9b6f1cb0c6bb29143329f601dfcfcb1`.

Apply `executorch-a72.patch` to the ExecuTorch source and `torchao-a72.patch` inside `third-party/ao`. The first targets Cortex-A72 for the custom LLM operators. The second uses the existing scalar quantized-matmul fallback when dot product is unavailable. Set `PILL_ARM_GNU_BIN` to the installed compiler bin directory. The build uses pinned sources, including the host FlatBuffers build, and disables optional KleidiAI in both XNNPACK and its ExecuTorch wrapper.

From the ExecuTorch source directory, set `PILL_BUILD` to an absolute writable build path, `PILL_TOOLCHAIN` to the absolute toolchain file, and `PILL_PYTHON` to the project virtual environment's Python executable, then run:

```sh
cmake --preset llm-release -B "$PILL_BUILD" -G Ninja \
  -DPILL_ARM_GNU_BIN="$PILL_ARM_GNU_BIN" -DCMAKE_TOOLCHAIN_FILE="$PILL_TOOLCHAIN" -DCMAKE_INSTALL_PREFIX="$PILL_BUILD" \
  -DPYTHON_EXECUTABLE="$PILL_PYTHON" -DEXECUTORCH_BUILD_EXTENSION_ASR_RUNNER=OFF \
  -DEXECUTORCH_BUILD_EXECUTOR_RUNNER=OFF -DXNNPACK_ENABLE_KLEIDIAI=OFF \
  -DEXECUTORCH_XNNPACK_ENABLE_KLEIDI=OFF
CMAKE_BUILD_PARALLEL_LEVEL=6 cmake --build "$PILL_BUILD"
cmake --install "$PILL_BUILD"
cmake -S examples/models/llama -B "$PILL_BUILD/examples/models/llama" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DPILL_ARM_GNU_BIN="$PILL_ARM_GNU_BIN" -DCMAKE_TOOLCHAIN_FILE="$PILL_TOOLCHAIN" \
  -DCMAKE_FIND_ROOT_PATH="$PILL_BUILD"
cmake --build "$PILL_BUILD/examples/models/llama" --parallel 4 --target llama_main
```

Stage `llama_main` and `runner/libllama_runner.so` in the same directory. Verify `ldd ./llama_main` on the Pi. The tested Pi system libraries provide glibc 2.41, libatomic, libgcc and libstdc++.
