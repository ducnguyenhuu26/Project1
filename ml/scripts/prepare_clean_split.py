"""Create an immutable, group-separated derivative of SWiM3 without editing the source.

Images are hardlinked where possible. Validation/test use one representative per
source family, avoiding inflated metrics from their augmented siblings.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

from audit_dataset import IMAGE_EXT, family


def clean_box(line: str):
    parts = line.split()
    if len(parts) != 5:
        return None, "columns"
    try:
        cls = int(parts[0]); x, y, w, h = map(float, parts[1:])
    except ValueError:
        return None, "parse"
    if cls not in (0, 1, 2) or not all(map(math.isfinite, (x, y, w, h))) or w <= 0 or h <= 0:
        return None, "class_or_size"
    x1, y1, x2, y2 = max(0, x-w/2), max(0, y-h/2), min(1, x+w/2), min(1, y+h/2)
    if x2 <= x1 or y2 <= y1:
        return None, "outside_image"
    new = (cls, (x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1)
    return f"{new[0]} {new[1]:.8f} {new[2]:.8f} {new[3]:.8f} {new[4]:.8f}", "clipped" if any(abs(a-b)>1e-7 for a,b in zip((x,y,w,h),new[1:])) else None


def prepare(source: Path, out: Path, seed: int = 42) -> dict:
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {out}")
    records=[]
    for old_split in ("train", "valid", "test"):
        for image in (source / old_split / "images").iterdir():
            if image.suffix.lower() in IMAGE_EXT:
                records.append((old_split,image,source / old_split / "labels" / f"{image.stem}.txt"))
    # Family stems catch Roboflow and local _augN siblings; content hashes catch
    # unrelated names that refer to the exact same pixels.
    by_hash=defaultdict(set)
    for index, (_, image, _) in enumerate(records):
        by_hash[hashlib.sha256(image.read_bytes()).digest()].add(index)
    parent=list(range(len(records)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(a,b):
        parent[root(a)]=root(b)
    seen={}
    for i,(_,image,_) in enumerate(records):
        key=family(image.stem)
        if key in seen: union(i,seen[key])
        else: seen[key]=i
    for indices in by_hash.values():
        first=next(iter(indices))
        for i in indices: union(first,i)
    groups=defaultdict(list)
    for i,record in enumerate(records): groups[root(i)].append(record)
    report={"seed":seed,"source":str(source.resolve()),"groups":len(groups),"splits":Counter(),"label_changes":Counter(),"dropped_augmented_eval":0,"manifest":[]}
    for group in groups.values():
        key=min(family(image.stem) for _,image,_ in group)
        r=int.from_bytes(hashlib.sha256(f"{seed}:{key}".encode()).digest()[:8],"big")/2**64
        target="train" if r<0.8 else "valid" if r<0.9 else "test"
        if target!="train":
            group=sorted(group,key=lambda rec: ("_aug" in rec[1].stem,rec[1].name))[:1]
        for original,image,label in group:
            name=f"{original}_{image.stem}"
            image_out=out/target/"images"/f"{name}{image.suffix.lower()}"
            label_out=out/target/"labels"/f"{name}.txt"
            image_out.parent.mkdir(parents=True,exist_ok=True)
            label_out.parent.mkdir(parents=True,exist_ok=True)
            try: os.link(image,image_out)
            except OSError: shutil.copy2(image,image_out)
            lines=[]
            for line_number, line in enumerate(label.read_text(encoding="utf-8-sig").splitlines(), 1):
                fixed,change=clean_box(line)
                if fixed is None:
                    raise ValueError(f"Cannot clean label {label}:{line_number} ({change})")
                lines.append(fixed)
                if change: report["label_changes"][change]+=1
            label_out.write_text("\n".join(lines)+("\n" if lines else ""),encoding="utf-8")
            report["splits"][target]+=1
            report["manifest"].append({"source_split":original,"source_name":image.name,"target_split":target,"target_name":image_out.name,"family":key})
    report["dropped_augmented_eval"]=len(records)-sum(report["splits"].values())
    yaml=f"path: {out.resolve().as_posix()}\ntrain: train/images\nval: valid/images\ntest: test/images\nnc: 3\nnames: {{0: Plastic, 1: Paper, 2: Metal}}\n"
    (out/"data.yaml").write_text(yaml,encoding="utf-8")
    (out/"manifest.json").write_text(json.dumps({**report,"splits":dict(report["splits"]),"label_changes":dict(report["label_changes"])},ensure_ascii=False,indent=2),encoding="utf-8")
    return {key:value for key,value in report.items() if key!="manifest"}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,default=Path("datasets/swim3/Splitted_Dataset"))
    parser.add_argument("--out",type=Path,default=Path("datasets/swim3_clean"))
    parser.add_argument("--seed",type=int,default=42)
    args=parser.parse_args()
    print(json.dumps(prepare(args.source,args.out,args.seed),default=dict,indent=2))
