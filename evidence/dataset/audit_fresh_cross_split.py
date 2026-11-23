from pathlib import Path
from PIL import Image
import numpy as np
import hashlib
import csv

ROOT = Path("/mnt/c/Users/<workspace-user>/Downloads/archive/PharmaVision dataset")
OUTPUT = Path("fresh_cross_split_candidates.csv")

SPLITS = ["train", "validation", "test"]
CLASSES = ["defective", "normal"]
EXTENSIONS = {".jpg", ".jpeg", ".png"}

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def phash(path, size=32, hash_size=8):
    image = Image.open(path).convert("L").resize((size, size))
    pixels = np.asarray(image, dtype=np.float32)

    x = np.arange(size)
    k = np.arange(size)[:, None]
    dct = np.cos(np.pi * (2*x + 1)*k / (2*size))
    dct[0] *= 1 / np.sqrt(2)
    dct *= np.sqrt(2 / size)

    transformed = dct @ pixels @ dct.T
    low = transformed[:hash_size, :hash_size]
    return low > np.median(low[1:, 1:])

def distance(a, b):
    return int(np.count_nonzero(a != b))

# Collect and hash every image
images = []

for split in SPLITS:
    for cls in CLASSES:
        folder = ROOT / split / cls

        if not folder.is_dir():
            raise FileNotFoundError(f"Missing folder: {folder}")

        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in EXTENSIONS:
                continue

            images.append({
                "split": split,
                "class": cls,
                "path": path,
                "sha": sha256(path),
                "phash": phash(path)
            })

print(f"Images loaded: {len(images)}")

# Compare only images from different splits
results = []

for i, a in enumerate(images):
    for b in images[i + 1:]:
        if a["split"] == b["split"]:
            continue

        d = distance(a["phash"], b["phash"])
        exact = a["sha"] == b["sha"]

        if exact or d <= 8:
            results.append([
                a["split"], a["class"], a["path"].name,
                b["split"], b["class"], b["path"].name,
                d, exact
            ])

# Save candidate pairs
with OUTPUT.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "split_A", "class_A", "image_A",
        "split_B", "class_B", "image_B",
        "phash_distance", "exact_sha256_match"
    ])
    writer.writerows(results)

print("\n===== FRESH DATASET AUDIT =====")

for pair in [
    ("train", "validation"),
    ("train", "test"),
    ("validation", "test")
]:
    selected = [
        r for r in results
        if (r[0], r[3]) == pair or (r[3], r[0]) == pair
    ]
    print(f"{pair[0]} vs {pair[1]}: {len(selected)} candidate pairs")

print("\n===== MATCH CLASSIFICATION =====")
print("Exact SHA-256 duplicates:",
      sum(1 for r in results if r[7]))
print("pHash candidates (distance <= 8):",
      sum(1 for r in results if not r[7]))

print("\n===== CLASS MISMATCH CANDIDATES =====")
mismatches = [r for r in results if r[1] != r[4]]
print("Count:", len(mismatches))

for r in mismatches[:30]:
    print(
        f"{r[0]}/{r[1]}/{r[2]} <-> "
        f"{r[3]}/{r[4]}/{r[5]} | "
        f"distance={r[6]} | exact={r[7]}"
    )

print("\nSaved report:", OUTPUT.resolve())
print("Original dataset was not modified.")
