from pathlib import Path
import cv2
import random

dataset_dir = Path("datasets/swim3/Splitted_Dataset")
image_dir = dataset_dir / "train" / "images"
label_dir = dataset_dir / "train" / "labels"

class_names = ["Plastic", "Paper", "Metal"]

# Select one image
image_paths = list(image_dir.glob("*.jpg"))
image_path = random.choice(image_paths)

label_path = label_dir / f"{image_path.stem}.txt"

image = cv2.imread(str(image_path))
if image is None:
    raise RuntimeError(f"Cannot read image: {image_path}")

height, width = image.shape[:2]

# Read YOLO annotations
with open(label_path, "r", encoding="utf-8") as file:
    for line in file:
        values = line.strip().split()

        if not values:
            continue

        class_id = int(values[0])
        xc, yc, w, h = map(float, values[1:5])

        # Convert normalized coordinates to pixels
        x1 = int((xc - w / 2) * width)
        y1 = int((yc - h / 2) * height)
        x2 = int((xc + w / 2) * width)
        y2 = int((yc + h / 2) * height)

        # Draw bounding box
        cv2.rectangle(
            image, (x1, y1), (x2, y2),
            (0, 255, 0), 2
        )

        # Draw class name
        cv2.putText(
            image,
            class_names[class_id],
            (x1, max(y1 - 10, 15)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

# Save annotated image
output_dir = Path("outputs/annotations")
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / image_path.name
cv2.imwrite(str(output_path), image)

print(f"Saved: {output_path.resolve()}")
