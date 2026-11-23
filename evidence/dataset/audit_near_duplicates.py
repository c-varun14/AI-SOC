from pathlib import Path
from PIL import Image
import numpy as np
import os
from collections import defaultdict

ROOT = Path(os.environ["PILLGUARD_DATA_ROOT"])

SPLITS = ["Train", "Train_augmented", "Val", "Test"]
CLASSES = ["defective", "normal"]

# Smaller distance means more visually similar.
# 0 = identical perceptual hash.
THRESHOLD = 5

def perceptual_hash(path, size=32, hash_size=8):
    image = Image.open(path).convert("L").resize((size, size))
    pixels = np.asarray(image, dtype=np.float32)

    # DCT using NumPy FFT-based cosine transform.
    def dct_matrix(n):
        x = np.arange(n)
        k = np.arange(n)[:, None]
        matrix = np.cos(np.pi * (2 * x + 1) * k / (2 * n))
        matrix[0] *= 1 / np.sqrt(2)
        return matrix * np.sqrt(2 / n)

    dct = dct_matrix(size)
    transformed = dct @ pixels @ dct.T

    low_freq = transformed[:hash_size, :hash_size]
    median = np.median(low_freq[1:, 1:])
    bits = low_freq > median

    return bits.flatten()

def hamming_distance(hash1, hash2):
    return int(np.count_nonzero(hash1 != hash2))

images = []

print("Reading images and calculating perceptual hashes...")

for split in SPLITS:
    for cls in CLASSES:
        folder = ROOT / split / cls

        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue

            try:
                images.append({
                    "split": split,
                    "class": cls,
                    "path": path,
                    "hash": perceptual_hash(path)
                })
            except Exception as error:
                print("ERROR:", path, error)

print(f"\nImages processed: {len(images)}")

print("\nComparing images across different splits...")

matches = []
for i in range(len(images)):
    for j in range(i + 1, len(images)):
        a, b = images[i], images[j]

        # Only compare different dataset splits.
        if a["split"] == b["split"]:
            continue

        distance = hamming_distance(a["hash"], b["hash"])

        if distance <= THRESHOLD:
            matches.append((distance, a, b))

matches.sort(key=lambda x: x[0])

report = Path("near_duplicate_report.txt")

with report.open("w") as f:
    f.write("PILLGUARD NEAR-DUPLICATE AUDIT\n")
    f.write(f"Threshold: {THRESHOLD}\n")
    f.write(f"Images processed: {len(images)}\n")
    f.write(f"Potential matches: {len(matches)}\n\n")

    for distance, a, b in matches:
        f.write(f"Distance: {distance}\n")
        f.write(f"  {a['split']}/{a['class']}/{a['path'].name}\n")
        f.write(f"  {b['split']}/{b['class']}/{b['path'].name}\n\n")

print("\n===== NEAR-DUPLICATE AUDIT RESULTS =====")
print("Potential cross-split matches:", len(matches))
print("Report saved:", report)

for distance, a, b in matches[:30]:
    print(f"\nDistance: {distance}")
    print(f"  {a['split']}/{a['class']}/{a['path'].name}")
    print(f"  {b['split']}/{b['class']}/{b['path'].name}")

print("\nAudit complete. No files were modified.")
