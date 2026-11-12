from ultralytics import YOLO

# 1. Load pretrained YOLO26 Nano
model = YOLO("yolo26n.pt")

# 2. Run inference on a sample image
results = model.predict(
    source="https://ultralytics.com/images/bus.jpg",
    imgsz=640,
    device="cpu",
    save=True,
    project="runs",
    name="smoke_test",
    exist_ok=True
)

# 3. Read predicted bounding boxes
for result in results:
    for box in result.boxes:
        class_id = int(box.cls.item())
        confidence = float(box.conf.item())

        class_name = result.names[class_id]

        print(
            f"Class: {class_name}, "
            f"Confidence: {confidence:.3f}"
        )
