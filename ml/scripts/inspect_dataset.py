
from pathlib import Path
from collections import Counter

dataset_dir = Path("datasets/swim3/Splitted_Dataset")

total_classes = Counter()

for split in ["train", "valid", "test"]:
    image_dir = dataset_dir / split / "images"
    label_dir = dataset_dir / split / "labels"

    images = list(image_dir.glob("*.jpg"))
    labels = list(label_dir.glob("*.txt"))

    class_counts = Counter()

    # Count every annotated object
    for label_file in labels:
        with open(label_file, "r", encoding="utf-8") as file:
            for line in file:
                values = line.strip().split()

                if not values:
                    continue

                class_id = int(values[0])
                class_counts[class_id] += 1

    # Check whether image and label names match
    image_names = {p.stem for p in images}
    label_names = {p.stem for p in labels}

    print(f"\n=== {split.upper()} ===")
    print(f"Images: {len(images)}")
    print(f"Labels: {len(labels)}")
    print(f"Images without labels: {len(image_names - label_names)}")
    print(f"Labels without images: {len(label_names - image_names)}")
    print(f"Class distribution: {dict(sorted(class_counts.items()))}")

    total_classes.update(class_counts)

print("\n=== TOTAL CLASS DISTRIBUTION ===")
for class_id, count in sorted(total_classes.items()):
    print(f"Class {class_id}: {count} objects")
