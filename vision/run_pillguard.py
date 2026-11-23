"""Run PillGuard JPEG preprocessing and ExecuTorch inference."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(
        description="PillGuard Experiment 2 image inference"
    )
    parser.add_argument("image", help="Path to a JPEG or PNG image")
    args = parser.parse_args()

    image = Path(args.image).expanduser().resolve()

    if not image.is_file():
        parser.error(f"Image not found: {image}")

    if image.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        parser.error("Supported image formats: JPG, JPEG, PNG")

    executable = PROJECT / "build/pillguard_deployment_inference"
    preprocessor = PROJECT / "preprocess_pill_deployment.py"

    if not executable.is_file():
        parser.error(f"Executable not found: {executable}")

    if not preprocessor.is_file():
        parser.error(f"Preprocessing script not found: {preprocessor}")

    print("=== PILLGUARD IMAGE INFERENCE ===", flush=True)
    print("Image:", image, flush=True)

    with tempfile.TemporaryDirectory(prefix="pillguard_") as tmp:
        tensor = Path(tmp) / "input.bin"

        subprocess.run(
            [
                sys.executable,
                str(preprocessor),
                str(image),
                "--output",
                str(tensor),
            ],
            cwd=PROJECT,
            check=True,
        )

        subprocess.run(
            [str(executable), str(tensor)],
            cwd=PROJECT,
            check=True,
        )

if __name__ == "__main__":
    main()
