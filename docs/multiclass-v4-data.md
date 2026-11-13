# Multiclass v4 dataset audit

## Result

`datasets/multiclass_v4/` combines the unchanged, audited `multiclass_v3` images and split assignments with one additional source: [GARBAGE CLASSIFICATION 3 v2](https://universe.roboflow.com/material-identification/garbage-classification-3/dataset/2). The source is published under CC BY 4.0 and provides 10,464 images in COCO box format. Source archives were downloaded from the Hugging Face mirror and verified against their SHA-256 digests before extraction.

The new source contains 74,090 annotation rows. Audit removed 17 zero-area boxes and found no missing images, out-of-bounds boxes, or duplicate images. The retained new-source set is 10,464 images / 74,073 boxes. A 12-image visual spot-check (two examples per source category) showed the expected semantic labels and boxes; this does not amount to a manual review of every annotation.

Recreate the download and build locally with:

```powershell
.\.venv\Scripts\python.exe ml\scripts\download_garbage_detection_hf.py
.\.venv\Scripts\python.exe ml\scripts\build_multiclass_v4.py
```

The downloader verifies every source ZIP by size and SHA-256. The builder refuses to overwrite an existing v4 output.

## Classes and mapping

Model class order is fixed in `data.yaml` and `taxonomy.json`:

| YOLO ID | Model class | New source class mapping | Total boxes | Train / val / test boxes |
|---:|---|---|---:|---:|
| 0 | plastic | plastic | 11,421 | 8,915 / 1,189 / 1,317 |
| 1 | paper | paper, cardboard | 9,083 | 7,192 / 1,019 / 872 |
| 2 | metal | metal | 5,931 | 4,777 / 512 / 642 |
| 3 | glass | glass | 7,854 | 6,110 / 852 / 892 |
| 4 | organic | biodegradable | 45,395 | 35,524 / 4,842 / 5,029 |
| 5 | cigarette_litter | retained from v3 | 31 | 24 / 3 / 4 |
| **Total** | | | **79,715** | **62,542 / 8,417 / 8,756** |

The `biodegradable` source category includes whole produce and food items in the sampled images. It is mapped to the broad `organic` category, but the model cannot infer whether produce is discarded or reliably identify a particular peel. No textile/clothing class was added; this model must not be described as detecting jackets.

## Split and leakage audit

The original v3 assignments are unchanged: 4,296 train, 558 validation, and 571 test images. The newly acquired source was reassigned deterministically with seed 42 and image-level multilabel stratification to approximately 80/10/10 because its supplied split had no glass in test and only 15 validation images containing paper. Related filenames are grouped before assignment. Combined split sizes are:

| Split | Images | Boxes |
|---|---:|---:|
| Train | 12,656 | 62,542 |
| Validation | 1,611 | 8,417 |
| Test | 1,622 | 8,756 |

All six classes occur in all splits. The manifest audit found zero cross-split filename-group leaks, zero cross-split exact-image duplicates, and zero exact duplicates between v3 and the new source. Test remains reserved for final evaluation after model selection.

`datasets/multiclass_v4/audit_report.json` records exact class/image counts and source audit details. `dataset_manifest.json` records per-image source, split, SHA-256, source labels, taxonomy mapping, and source annotation IDs. Its SHA-256 is `d3fd7a57749d2e8d6625c8d822db81d471225c8f081c2bbe1298f62cf67f8a50`.

## What is ready and what is not

The six-class dataset passes structural readiness: valid YOLO boxes, a matching class order, all classes represented in train/validation/test, retained provenance, and no detected split leakage. The dataset source is international, not Vietnam-specific. A future Vietnam field set is still needed to measure domain performance. `organic` has 45,395 boxes but is visually dominated by source-defined biodegradable produce; this count is not a measure of banana-peel coverage. `cigarette_litter` remains small at 31 boxes. Do not claim good metrics before training and held-out evaluation.

The build preserves `multiclass_v3`, `multiclass_v2`, and the SWiM3 baseline. No GPU training has been started. Use the CPU preflight and Vast.ai handoff in [the runbook](vast-runbook.md) when the dataset is transferred.
