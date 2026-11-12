# Vietnam-relevant detection data expansion

Updated 2026-11-13. No paid GPU session or training run was started. This addendum preserves the previously audited `multiclass_v2` corpus and the SWiM3 baseline.

## Added source: KNR-PET-7

The [Mendeley Data record](https://data.mendeley.com/datasets/5x9bzrk9ch/2) describes more than 5,000 images of post-consumer PET bottles captured at an operating recycling facility in Vietnam, with YOLO oriented bounding boxes for seven industrial bottle grades. The released archive says 5,424 images and 5,425 object instances. Its license file states CC BY 4.0; retain attribution and the source URL when reusing it. The archive SHA-256 verified against the record API is `46dc8bbb3643d56bc4a8930137df23cfacb1c0c5607b86272052e19783dafbd3`.

The source categories `B1`, `B2.1`, `B2.2`, `B3`, `B4`, `B5`, and `B6` are all PET-bottle grades. They are mapped to the existing broad `plastic` model class; no grade is presented as a different material. Original grade IDs, source file names, split, and source hashes remain in the output manifest. OBB polygons are converted to enclosing axis-aligned YOLO boxes without changing coordinates or image dimensions. BMP images are converted to JPEG quality 95 for the existing training preflight's supported formats.

## Dataset audit and deduplication

Source audit results:

- 5,424 images and 5,424 paired labels; 5,425 source boxes.
- Image dimensions: all 1,920 × 1,200. Formats: 4,870 JPEG and 554 BMP.
- All 5,425 lines parse with valid class IDs and normalized corner coordinates; the source labels use UTF-8 BOM in some files, handled with `utf-8-sig`.
- Source box counts: B1 903, B2.1 1,105, B2.2 1,226, B3 496, B4 193, B5 359, B6 1,143.
- The archive passed WinRAR's integrity test; its complete archive hash matched the source API.
- Exact-byte duplicates occurred within and across the source splits. 248 duplicate records were removed. In 85 duplicate groups the same image appeared in multiple official splits; the retained copy stays in the highest-priority existing split (`test`, then `val`, then `train`) and the other copies are removed.
- Eight additional duplicate groups had conflicting source class IDs or materially different boxes. All images in those groups were excluded from training and recorded for human review. Same-class duplicate boxes with IoU ≥ 0.85 were merged by taking their union; the source OBB labels remain untouched in the extracted archive.

## Combined YOLO dataset

The new output is `datasets/multiclass_v3/`; `datasets/multiclass_v2/` remains unchanged. The original TACO split assignments and KNR-PET-7 split assignments are retained. The merged dataset has zero exact duplicate images across splits and zero manifest group leakage.

| Class | Train boxes | Validation boxes | Test boxes | Total boxes | Images containing class |
|---|---:|---:|---:|---:|---:|
| plastic | 4,336 | 564 | 576 | 5,476 | 5,351 |
| metal | 75 | 8 | 7 | 90 | 48 |
| glass | 16 | 27 | 2 | 45 | 13 |
| cigarette_litter | 24 | 3 | 4 | 31 | 23 |
| **All** | **4,451** | **602** | **589** | **5,642** | — |

The combined dataset contains 4,296 train, 558 validation, and 571 test images (5,425 total), from 5,160 retained KNR-PET-7 images and 265 TACO ODbL images. Eighteen empty-label TACO images are intentional fully annotated negatives. All four target classes occur in every split, but glass and cigarette-litter validation/test counts remain too small for a strong quality claim. The added Vietnam source only expands `plastic`; it does not establish detection support for banana peels, clothing, or general mixed household rubbish.

The readiness report and per-image source/hash/box provenance are in `datasets/multiclass_v3/readiness_report.json` and `datasets/multiclass_v3/dataset_manifest.json`. The combined manifest SHA-256 is `2b4e408bf3efaedfeea1c92bce04af11c6a5c74ed0c75ab08c02545bbd27f614`.

## Rebuild and CPU preflight

```powershell
.\.venv\Scripts\python.exe ml\scripts\download_mendeley_pet7.py --root datasets\knr_pet7\raw
& 'C:\Program Files\WinRAR\UnRAR.exe' x -o+ -inul datasets\knr_pet7\raw\KNR-PET-7_dataset_v2.rar datasets\knr_pet7\extracted\
.\.venv\Scripts\python.exe ml\scripts\merge_knr_pet7.py --base datasets\multiclass_v2 --pet-root datasets\knr_pet7\extracted --out datasets\multiclass_v3
.\.venv\Scripts\python.exe ml\scripts\train_multiclass.py --data datasets\multiclass_v3\data.yaml --model outputs\cpu_smoke\cpu-smoke-yolo26n-1ep-final\weights\best.pt --name multiclass-v3-readiness-check --device cpu --preflight-only --min-free-gb 1
```

The CPU preflight passed: all four classes are present in all splits, manifest image hashes match, and no exact-image or group leakage was found. It did not train a model. The supplied checkpoint is the existing one-epoch smoke checkpoint and must not be deployed or treated as a quality result. Training on Vast.ai remains a separate paid GPU run and has not started.

The complete repository test suite passed after this change: 38 passed, with one existing Starlette/httpx deprecation warning. The new KNR importer unit tests cover OBB-to-box conversion, invalid labels, filename/class consistency, duplicate box merging, and conflicting classes.

## Sources reviewed but not merged

- [pLitterStreet](https://zenodo.org/records/8288500) has 13,064 labeled street images, but the annotation paths identify locations in Thailand and Sri Lanka, not Vietnam. Its categories also include object types such as bottle and cup whose material is not always specified. It was excluded from the Vietnam material training set.
- RiverPlasticDataset's GitHub page identifies Vietnam, Indonesia, and the Netherlands and 13 object classes, including plastic items, glass bottles, and metal cans. Its 680,388,727-byte archive passed the published MD5 and ZIP CRC checks. The Vietnam subset contains 206 paired images/labels (145 train / 41 validation / 20 test) and 2,401 boxes: 951 unclassified plastic, 141 plastic bottle, 190 plastic bag, 344 food container/cutlery, 290 plastic straw, 109 transparent bag, 120 food wrapper, 94 bottle-cap/container, 121 polystyrene, 21 drink carton, 14 glass bottle, 4 metallic can, and 2 rubber ball. The files have no missing/orphan pairs or hard-invalid boxes. Thirty boxes overshoot an image edge by at most 0.000003 due to coordinate rounding; if reused, clip these boundary-only deviations and record the transform. The paper describes these as river images from Ho Chi Minh City with a vertical camera view and vegetation/water backgrounds, so they are a separate river domain rather than household-trash examples. The GitHub `LICENSE.md` states CC BY-SA 4.0 while its Zenodo record advertises CC BY 4.0; source-by-source rights remain unresolved. The archive stays separate and was not merged into v3.
- Image-classification-only sources do not provide bounding boxes. Their whole-image class label is not converted into an object-detection box.

The old baseline, split manifests, and earlier model artifacts are not overwritten by this preparation.
