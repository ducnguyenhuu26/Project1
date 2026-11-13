# Multiclass v5 dataset audit

## Current train input

`datasets/multiclass_v5/` extends the audited six-class v4 corpus with images from [MRS Trash Detection](https://www.modelscope.cn/datasets/YizheDev/trash_detection). ModelScope identifies the dataset license as Apache License 2.0; the [Hugging Face mirror](https://huggingface.co/datasets/alexNova/MRS-Trash-Detection) also declares Apache-2.0 and supplies the class IDs and stratified train/val/test labels.

The full MRS mirror has 9,285 labeled images and 16,669 boxes across ten classes. `Textile` occurs in 1,103 images with 1,258 boxes. Only images whose complete annotation file contains `Textile` boxes and no other category are considered. This avoids using images containing other annotated classes as if those objects were background. Source labels selected 1,041 images / 1,179 boxes; LFS verified downloaded image content against repository object hashes. Exact hashing then found 7 duplicate image records, including 3 copies crossing the official train/validation/test partitions. All 7 were excluded, leaving 1,034 images / 1,171 boxes: 831 train, 161 validation, and 179 test. The other 8,244 MRS images were excluded because they are not Textile-only.

The source split is preserved for nonduplicate items: 725 / 148 / 161 Textile images. A 12-image spot-check showed textile boxes on clothes, fabric household objects and plush toys. Therefore `textile` is a material/object group, not an exact “discarded jacket” class. Jackets occur in the source, but no jacket-specific count or quality claim is made.

## Classes and counts

The fixed v5 model order is `plastic`, `paper`, `metal`, `glass`, `organic`, `textile`, `cigarette_litter`.

| Class | Total boxes | Train / val / test boxes | Train / val / test images containing class |
|---|---:|---:|---:|
| plastic | 11,421 | 8,915 / 1,189 / 1,317 | 5,409 / 696 / 710 |
| paper | 9,083 | 7,192 / 1,019 / 872 | 2,596 / 324 / 324 |
| metal | 5,931 | 4,777 / 512 / 642 | 1,556 / 195 / 195 |
| glass | 7,854 | 6,110 / 852 / 892 | 2,156 / 270 / 271 |
| organic | 45,395 | 35,524 / 4,842 / 5,029 | 1,829 / 229 / 229 |
| textile | 1,171 | 831 / 161 / 179 | 725 / 148 / 161 |
| cigarette_litter | 31 | 24 / 3 / 4 | 18 / 2 / 3 |
| **All boxes** | **80,886** | **63,373 / 8,578 / 8,935** | — |

Combined split sizes are 13,381 train / 1,759 validation / 1,783 test images (16,923 total). All seven classes appear in each split. v4 assignments are unchanged. MRS split assignments are preserved from its stratified source release after exact deduplication. The builder hashes v4 and new source images and records duplicate exclusions; the final audit found zero cross-split group leaks and zero cross-split exact duplicates. Dataset manifest SHA-256: `aee7cb8cf3ee59fd7d034230dcf1329f7d34c08df4f3b3646367faa867171bed`.

## Limits and reproducibility

The combined corpus is international, not Vietnam-specific. The Roboflow `biodegradable` class maps to broad `organic` and includes whole produce; it is not a banana-peel benchmark. MRS `Textile` also covers plush toys, pillows and fabric objects, so it can fire on reusable household goods. `cigarette_litter` remains small. Train first, then evaluate the frozen checkpoint on the held-out test split before making user-facing performance claims.

CPU training smoke: YOLO26s trained for one epoch on a 42-image subset (14 images per split, all seven classes present). It produced `best.pt`, `last.pt`, and a model manifest with the correct seven-class order and taxonomy `2026-11-13.2`. Validation mAP50 was 0.0322 on the tiny 14-image validation slice; this is only pipeline evidence and has no model-quality meaning. No GPU job was started.

Recreate the source subset and dataset locally:

```powershell
.\.venv\Scripts\python.exe ml\scripts\download_mrs_textile_source.py
.\.venv\Scripts\python.exe ml\scripts\build_multiclass_v5.py
```

The downloader fetches the Hugging Face metadata/labels and only the Textile-only images. The builder refuses to overwrite an existing v5 output and preserves v4/v3/SWiM3.
