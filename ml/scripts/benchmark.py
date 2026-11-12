"""Measure warm CPU/GPU inference time on one image; includes preprocessing/postprocessing."""
import argparse
import json
from pathlib import Path
import statistics
from time import perf_counter

from PIL import Image
from ultralytics import YOLO


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--image",type=Path,required=True)
    p.add_argument("--device",default="cpu")
    p.add_argument("--imgsz",type=int,default=640)
    p.add_argument("--runs",type=int,default=30)
    p.add_argument("--out",type=Path,default=Path("outputs/benchmark.json"))
    a=p.parse_args()
    if a.runs<5: p.error("runs must be at least 5")
    model=YOLO(str(a.model.resolve()))
    with Image.open(a.image) as im: image=im.convert("RGB")
    for _ in range(5): model.predict(image,device=a.device,imgsz=a.imgsz,verbose=False)
    times=[]
    for _ in range(a.runs):
        t=perf_counter(); model.predict(image,device=a.device,imgsz=a.imgsz,verbose=False)
        if a.device!="cpu":
            import torch
            if torch.cuda.is_available(): torch.cuda.synchronize()
        times.append((perf_counter()-t)*1000)
    times.sort()
    output={"model":str(a.model),"device":a.device,"imgsz":a.imgsz,"image_size":image.size,
            "runs":a.runs,"median_ms":statistics.median(times),"p95_ms":times[min(len(times)-1,int(a.runs*.95))]}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(output,indent=2),encoding="utf-8")
    print(json.dumps(output,indent=2))


if __name__=="__main__": main()
