from pathlib import Path
from PIL import Image
import numpy as np

import argparse

parser = argparse.ArgumentParser(
    description="Preprocess a pill image for PillGuard ExecuTorch"
)
parser.add_argument("image", help="Input JPEG or PNG image")
parser.add_argument(
    "--output",
    default="test_images/pill_input.bin",
    help="Output float32 tensor path"
)
args = parser.parse_args()

image_path = Path(args.image)
output_path = Path(args.output)

if not image_path.is_file():
    parser.error(f"Image not found: {image_path}")

output_path.parent.mkdir(parents=True, exist_ok=True)

image = Image.open(image_path).convert("RGB")
image = image.resize((224, 224), Image.Resampling.BILINEAR)

pixels = np.asarray(image, dtype=np.float32) / 255.0

mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

pixels = (pixels - mean) / std

tensor = np.transpose(pixels, (2, 0, 1))
tensor = np.ascontiguousarray(tensor, dtype=np.float32)

tensor.tofile(output_path)

print("Preprocessing SUCCESS")
print("Input:", image_path)
print("Output:", output_path)
print("Tensor shape:", tensor.shape)
print("Tensor dtype:", tensor.dtype)
print("Output bytes:", output_path.stat().st_size)
