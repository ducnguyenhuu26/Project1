"""Compare validation metrics; never reads test by default."""
import argparse
import json
from pathlib import Path


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("reports",type=Path,nargs="+")
    a=p.parse_args()
    rows=[]
    for path in a.reports:
        report=json.loads(path.read_text(encoding="utf-8"))
        if report.get("split")!="val": p.error(f"Only validation reports may be compared: {path}")
        rows.append((path.name,report["map50_95"],report["map50"],report["precision"],report["recall"]))
    print("report\tmAP50:95\tmAP50\tprecision\trecall")
    for row in sorted(rows,key=lambda r:r[1],reverse=True):
        print("\t".join([row[0],*[f"{v:.4f}" for v in row[1:]]]))
