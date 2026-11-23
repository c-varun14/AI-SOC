from pathlib import Path
from PIL import Image
import numpy as np
import os
import csv

old = Path(os.environ["PILLGUARD_DATA_ROOT"])
fresh = Path("/mnt/c/Users/<workspace-user>/Downloads/archive/PharmaVision dataset")

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

extensions = {".jpg", ".jpeg", ".png"}

fresh_images = []
for split in ["train", "validation", "test"]:
    for cls in ["defective", "normal"]:
        folder = fresh / split / cls
        for path in folder.iterdir():
            if path.suffix.lower() in extensions:
                fresh_images.append((split, cls, path))

print("Hashing fresh dataset...")
fresh_hashes = [
    (split, cls, path, phash(path))
    for split, cls, path in fresh_images
]

old_test = []
for cls in ["defective", "normal"]:
    folder = old / "Test" / cls
    for path in folder.iterdir():
        if path.suffix.lower() in extensions:
            old_test.append((cls, path))

print("Comparing old Test against fresh dataset...")
rows = []

for index, (old_class, old_path) in enumerate(old_test, 1):
    old_hash = phash(old_path)
    matches = []

    for split, fresh_class, fresh_path, fresh_hash in fresh_hashes:
        d = distance(old_hash, fresh_hash)
        matches.append((d, split, fresh_class, fresh_path))

    matches.sort(key=lambda x: x[0])

    for rank, (d, split, fresh_class, fresh_path) in enumerate(matches[:3], 1):
        rows.append([
            str(old_path.relative_to(old)),
            old_class,
            rank,
            d,
            split,
            fresh_class,
            str(fresh_path.relative_to(fresh))
        ])

    if index % 25 == 0:
        print(f"Processed {index}/{len(old_test)} old Test images")

output = Path("old_test_fresh_nearest_matches.csv")

with output.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "old_test_image", "old_class", "rank", "distance",
        "fresh_split", "fresh_class", "fresh_image"
    ])
    writer.writerows(rows)

print("\n===== AUDIT SUMMARY =====")
for threshold in [0, 3, 5, 8]:
    count = sum(
        1 for row in rows
        if row[2] == 1 and row[3] <= threshold
    )
    print(f"Old Test images with nearest match distance <= {threshold}: {count}")

print("\nSaved:", output.resolve())
print("No dataset files were modified.")
