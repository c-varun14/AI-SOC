# Setup and reproducibility

## WSL reviewer check

Use Python 3.12 and localhost access in WSL. Initialize a virtual environment if the pinned dependencies are unavailable. An offline reviewer can install from a separately prepared wheelhouse for their Python and architecture.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-wsl.txt
python app/app.py --help
python vision/run_pillguard.py --help
python -m unittest discover -s tests -v
python evidence/dataset/evaluate.py evidence/dataset/*predictions.csv
```

The HTTP test creates synthetic images and runs the shipped Pillow/NumPy preprocessor. Its two native subprocesses are controlled stand-ins. It checks the preserved prompt, PASS and FAIL QC decisions, rejection of unsupported advisory output, and SQLite export. The metrics command recomputes the archived dataset scores from saved predictions. These checks establish code and evidence reproducibility. Real inference evidence is independent of the stand-ins.

A WSL native vision build can be configured with an x86-64 ExecuTorch 1.6.0 CPU wheel supplying the CMake SDK, CMake 3.28+ and a C++17 compiler. Set `ET_CMAKE_DIR` to the folder containing `executorch-config.cmake`, typically `<venv>/lib/python3.12/site-packages/executorch/lib/cmake/executorch`. Run the CMake commands below using the WSL wheel. ARM64 runners require an ARM64 system or explicit cross-compilation. Existing logs show real ARM64 runs. A fresh installation of the complete ARM64 SDK and hardware test are outside this WSL review.

## Raspberry Pi, only for later authorized verification

The verified device ran 64-bit Raspberry Pi OS based on Debian 13. It had Python 3.13 with Pillow and NumPy, an ExecuTorch 1.6.0 AArch64 vision SDK, and a separate Cortex-A72 Llama runner. Use a fresh checkout, fresh data directory and spare loopback port. Avoid the deployed ports 8765 and 8766 for review. Use read-only copies or symlinks for authorized model artifacts under their recorded filenames.

1. Install or locate the matching AArch64 ExecuTorch SDK. Record the exact version and locate its CMake configuration.
2. Build the single-pass wrapper from this checkout, or stage the already verified AArch64 vision binary and its runtime dependencies. Confirm ELF architecture and runtime resolution with `file` and `ldd`.
3. Place the matching vision and Llama `.pte` files in `vision/`. Use the original tokenizer and the warmed-up CPU runner located outside the checkout. Keep `libllama_runner.so` beside `llama_main`. Verify artifacts against [the deployed hashes](../evidence/pi-sha256.txt) and [optimized binary manifest](../evidence/verified-optimized.sha256). Rebuilt files may differ in bytes. Record new hashes and benchmark results before treating a rebuild as verified.
4. Start the app on a spare local port and use authorized labeled uploads. Preserve the verified production services and history. Use pending test labels for any new run.

```sh
cmake -S vision -B vision/build -Dexecutorch_DIR="$ET_CMAKE_DIR"
cmake --build vision/build --parallel 2
python3 app/app.py --vision-dir vision --llama-runner "$LLAMA_MAIN" \
  --tokenizer "$LLAMA_TOKENIZER" --data-dir .review-data --port 18773
```

Open `http://127.0.0.1:18773` in the browser connected to the review instance. Upload an authorized normal JPEG or PNG, confirm that a tablet is visible, and select **Inspect selected image**. Repeat with an authorized defective image and compare both decisions and advisories with the archived upload evidence. Open the inspection history and download the JSON export. The browser also offers **Open video** and **Capture video frame** for a selected frame from a recording. The archived acceptance and walkthrough use image uploads. [Recorded demo and acceptance evidence](../evidence/README.md) · [Llama cross-build](../models/llama-build/README.md) · [Prior deployment and rollback reference](DEPLOYED-REFERENCE.md)
