# Multiclass YOLO26 readiness report

Updated 2026-11-12. This report records the local preparation and CPU smoke run. No paid GPU training was started. It is an engineering readiness check, not an accuracy claim.

## Source and label policy

- Source: TACO (Trash Annotations in Context), manually labeled outdoor litter images in COCO format. TACO describes 1,500 images, 60 sparse categories, and warns that many source categories have few annotations; see the [official TACO repository](https://github.com/pedropro/TACO).
- The source annotation file contains 1,500 images and 4,784 object annotations. Its SHA-256 is `812c2e3f0d336b437f276597715de2abb08bb8a641599c45f593d233ec66457b`.
- Only the exact image license label `ODBL (c) OpenLitterMap & Contributors` is allowlisted. Of the 1,500 source records, 466 were downloaded; 715 with no image license and 319 marked only generic `CC` were not downloaded. The annotation/source metadata and the dataset card describe image rights as varying; consult the source rights before any use beyond academic/non-commercial work.
- Category mapping is explicit in `ml/config/dataset_sources.json`. Ambiguous/composite/hazardous/unlabeled objects invalidate their whole image rather than silently becoming background. One invalid box was rejected. Among allowlisted/buildable images, exact duplicates: 0; near duplicates: 0; missing/unreadable files and dimension mismatches: 0. Paper/cardboard stays in the SWiM3 baseline and manual knowledge; it is not a new YOLO class because only 19 candidate boxes survived the first audit.
- New model taxonomy: `plastic`, `metal`, `glass`, `cigarette_litter`. “Cigarette” is an object-type label, not a recyclable material. Advice warns users not to touch a lit/hot butt and routes a confirmed cool butt to residual waste. This does not imply that the picture can determine whether it is hot.

## Final audited data counts

The builder retained 265 of 466 downloaded ODbL images (1.24 GB in this checkout). “Images” below counts images containing at least one box for that class; “boxes” counts reviewed target boxes. An image can contain multiple classes.

| Class | Source and reviewed mapping | Images train/val/test | Boxes train/val/test | Image license status | Ready? | Blocker |
|---|---|---:|---:|---|---|---|
| plastic | TACO explicit plastic/material categories → `plastic` | 153 / 19 / 19 | 250 / 34 / 32 | ODbL-marked images only | Yes for training | Outdoor-domain gap; grouped plastic objects are not a recycling guarantee |
| metal | TACO explicit metal object/material categories → `metal` | 38 / 5 / 5 | 75 / 8 / 7 | ODbL-marked images only | Yes for training | Low volume and outdoor-domain gap |
| glass | TACO glass bottle/cup/jar/broken glass → `glass` | 9 / 2 / 2 | 16 / 27 / 2 | ODbL-marked images only | Yes for smoke/training; weak evaluation | Only 9 train images; validation/test each contain two images |
| cigarette_litter | TACO `Cigarette` → object type `cigarette_litter` | 18 / 2 / 3 | 24 / 3 / 4 | ODbL-marked images only | Yes for smoke/training; weak evaluation | Only 18 train images; image cannot establish whether a butt is hot |
| **All target boxes** | **TACO ODbL subset** | **210 / 28 / 27 unique images** | **365 / 72 / 45** | **466 source images downloaded; 265 retained** | **Technical gate passed** | **Severe class imbalance; no accuracy claim** |

Image split: train 210, validation 28, test 27. All four classes occur in every split. Cross-split scene/group leaks: 0; exact duplicate image leaks: 0. Audit issue counts: 1,034 license-not-allowlisted source records, 402 annotation-level `needs_review` labels, 65 explicit excludes, 41 JPEG normalizations, 18 retained fully annotated negatives, and 1 invalid box. These are issue records, not unique image counts.

**Readiness:** ready for a controlled training run and artifact pipeline; not ready to claim balanced or field-quality performance. Glass has only 9 training images and 2 validation/test images each; cigarette litter has only 18 training images and 2/3 validation/test images. Glass validation’s 27 boxes are concentrated in two images. The test split is reserved and has not been used for model selection.

Re-fetch the strict-license image subset and rebuild it locally with:

```powershell
.\.venv\Scripts\python.exe ml/scripts/download_taco.py --root datasets/taco --workers 6
.\.venv\Scripts\python.exe ml/scripts/build_multisource.py --config ml/config/dataset_sources.json --out datasets/multiclass_v2
```

Artifacts and reproducibility:

- Dataset YAML: `datasets/multiclass_v2/data.yaml` (`path: .`, builder resolves it relative to this YAML; trainer writes an absolute runtime YAML for Ultralytics on Windows/Linux).
- Dataset manifest SHA-256: `05f9975536a240e6c0dbe1d32cfb330526631e77ae72a2af9fedf53fe0c82efd`.
- Taxonomy version: `2026-11-12.3`.
- Split seed: `42`; ratios: 80/10/10; scene groups remain intact.
- YOLO26n initialization checkpoint SHA-256 for the local smoke: `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.
- Tiny smoke subset manifest SHA-256: `6901b87c4275d206a4c3798dbb7d01d5d8cbc08f698c15ed7b9ee78ac3581af1`.

## Local verification

- Dataset builder: completed from the downloaded, license-filtered source. `ready_for_training=true`; all target labels passed coordinate/class validation. Forty-one source JPEGs had a noncanonical trailer; the builder normalized them into valid JPEGs and records `jpeg_repaired=41`. Ultralytics no longer mutates built images after hashing.
- Training preflight: passed on CPU with the final `datasets/multiclass_v2/data.yaml` audit; training had not started at that point; disk availability was about 125 GiB. Every generated image SHA-256 matched `dataset_manifest.json`.
- Tiny CPU smoke: a deterministic subset of real data (first two class-containing images per class in each original split), 22 images total: 7 train / 7 validation / 8 test, with all four classes in every split. `yolo26n.pt`, 1 epoch, batch 2, image size 256. Validation used 7 images / 37 boxes: precision 0.011, recall 0.359, mAP50 0.060, mAP50-95 0.026. These low one-epoch metrics only show code execution. Output: `outputs/cpu_smoke/cpu-smoke-yolo26n-tiny-1ep/`.
- Full-data CPU integration smoke: `yolo26n.pt`, 1 epoch, batch 4, image size 256, 210 train / 28 validation images. Validation: precision 0.720, recall 0.165, mAP50 0.125, mAP50-95 0.0746. These values are not evidence the model is useful; per-class metrics are especially unstable at 2 validation images for glass and cigarette litter.
- Smoke output files: `outputs/cpu_smoke/cpu-smoke-yolo26n-1ep-final/results.csv`, `outputs/cpu_smoke/cpu-smoke-yolo26n-1ep-final/model_manifest.json`, and `outputs/cpu_smoke/cpu-smoke-yolo26n-1ep-final/weights/best.pt` (gitignored; do not deploy).
- Backend/frontend contract: production frontend build succeeded; backend tests cover multi-class scans, health class support, advice and taxonomy mappings. An additional deployment-helper + local `TestClient` run installed and loaded the smoke checkpoint through `RealYOLODetector`, returned `model_status=ready`, all four supported IDs, and a successful `/api/v1/scans` response with two detections and linked advice.
- Full local test suite: 26 passed (one Starlette/httpx deprecation warning).
- Vast shell scripts: `bash -n scripts/vast_preflight.sh scripts/vast_train.sh` passed.

The CPU checkpoint under `outputs/cpu_smoke/` is a smoke artifact. Do not deploy it. Use the workflow in `docs/vast-runbook.md` for a full GPU run, then install only after validation and a separate held-out test evaluation.

One-run Vast command after transfer and successful preflight: `bash scripts/vast_train.sh`. Install the returned selected checkpoint with `python scripts/install_model.py --checkpoint imported-model/wastewise-taco-odbl-yolo26s-v2/weights/best.pt --manifest imported-model/wastewise-taco-odbl-yolo26s-v2/weights/model_manifest.json --weights-dir weights/models`.

## Known blockers / next evidence needed

1. The current licensed corpus is outdoors and has severe class imbalance; acquire and review a larger, rights-cleared source with more household glass and cigarette-litter examples before making consumer-facing quality claims.
2. Run the documented full YOLO26 training on Vast.ai only when a paid GPU session is explicitly intended. No GPU spend has happened in this task.
3. After model selection, evaluate the frozen checkpoint once on the untouched test split and record per-class precision/recall/AP, confusion and failure examples before deployment.
4. Verify use rights for every source image in any redistribution/commercial deployment. TACO’s image licenses vary; the allowlist is strict, but this report is not legal advice.
