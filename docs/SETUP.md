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

## Raspberry Pi deployment

The measured device used 64-bit Raspberry Pi OS based on Debian 13, Python 3.13 with Pillow and NumPy, an ExecuTorch 1.6.0 AArch64 vision SDK, and a Cortex-A72 Llama runner. For a separate evaluation instance, use a fresh checkout, data directory and loopback port. The matching model, tokenizer and runtime artifacts are identified in [the Pi manifest](../evidence/pi-sha256.txt).

1. Install or locate the matching AArch64 ExecuTorch SDK and its CMake configuration.
2. Build the vision wrapper from this checkout, or provide a compatible AArch64 binary and runtime libraries. Confirm architecture and library resolution with `file` and `ldd`.
3. Place the matching vision and Llama model files in `vision/`. Point the service to the original tokenizer and runner. Compare deployed artifacts with the recorded hashes; rebuilds can have different hashes and need their own measurements.
4. Start the service on a loopback port and inspect labeled uploads. Review the decision, history and JSON export.

```sh
cmake -S vision -B vision/build -Dexecutorch_DIR="$ET_CMAKE_DIR"
cmake --build vision/build --parallel 2
python3 app/app.py --vision-dir vision --llama-runner "$LLAMA_MAIN" \
  --tokenizer "$LLAMA_TOKENIZER" --data-dir .review-data --port 18773
```

Open `http://127.0.0.1:18773` in a browser connected to the evaluation instance. The browser also offers video-frame capture. The archived acceptance and walkthrough use image uploads. [Recorded demo and acceptance evidence](../evidence/README.md) · [Llama cross-build](../models/llama-build/README.md) · [Deployment map](DEPLOYED-REFERENCE.md)
