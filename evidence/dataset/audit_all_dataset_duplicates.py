from pathlib import Path
from collections import defaultdict
import os
import hashlib

ROOT = Path(os.environ.get(
    "PILLGUARD_DATA_ROOT",
    "/mnt/c/Users/<workspace-user>/Downloads/PharmaVision/PharmaVision"
))

SPLITS = ["Train", "Train_augmented", "Val", "Test"]
CLASSES = ["defective", "normal"]
EXTENSIONS = {".jpg", ".jpeg", ".png"}

hash_locations = defaultdict(list)
counts = defaultdict(int)

print("===== PILLGUARD FULL EXACT-DUPLICATE AUDIT =====")

for split in SPLITS:
    for class_name in CLASSES:
        folder = ROOT / split / class_name

        if not folder.is_dir():
            print("MISSING FOLDER:", folder)
            continue

        for path in folder.iterdir():
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                continue

            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hash_locations[digest].append((split, class_name, path.name))
            counts[(split, class_name)] += 1

print("\nIMAGE COUNTS")
for split in SPLITS:
    for class_name in CLASSES:
        print(f"{split:15} {class_name:10} "
              f"{counts[(split, class_name)]}")

print("\nCROSS-SPLIT EXACT DUPLICATES")

cross_split = []
for digest, locations in hash_locations.items():
    splits = {item[0] for item in locations}
    if len(splits) > 1:
        cross_split.append(locations)

print("Duplicate hash groups across splits:", len(cross_split))

for group in cross_split[:30]:
    print("\nDuplicate group:")
    for split, class_name, filename in group:
        print(f"  {split}/{class_name}/{filename}")

print("\nCROSS-CLASS EXACT DUPLICATES")

cross_class = []
for digest, locations in hash_locations.items():
    classes = {item[1] for item in locations}
    if len(classes) > 1:
        cross_class.append(locations)

print("Duplicate hash groups across classes:", len(cross_class))

for group in cross_class[:30]:
    print("\nDuplicate group:")
    for split, class_name, filename in group:
        print(f"  {split}/{class_name}/{filename}")

print("\nAudit complete. No files were modified.")
