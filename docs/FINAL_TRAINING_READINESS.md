# WasteWise VN — final pre-training readiness

**Decision: GO FOR FULL TRAINING after the Kaggle notebook preflight passes.** No paid GPU run was started here. The local dataset, code paths, and CPU smoke are reviewable; GPU VRAM, actual one/two-GPU smoke, Kaggle output persistence, and full training remain checks for the next Kaggle session.

## Frozen training dataset

The primary v5 dataset had seven classes, but `cigarette_litter` is not adequately represented for detection: 24 boxes in 18 train images, 3 boxes in 2 validation images, and 4 boxes in 3 test images. Those 23 images also contain 32 target boxes from other classes (plastic 22, metal 6, glass 4; counts overlap images because an image can contain several objects). Leaving cigarette annotations out would turn cigarettes into unlabeled background; retaining the class would not provide useful validation. Therefore the final detector uses six classes and drops all 23 cigarette-containing images. The full cross-split foreground hash audit also found and visually reviewed 23 near-duplicate candidate pairs; both images from each pair were removed before resealing final splits (45 unique images). The original `datasets/multiclass_v5` and intermediate six-class v6 remain unchanged. Cigarette litter remains in the backend Knowledge Base and taxonomy as a manual-lookup category (`detection_supported: false`).

Final model order: `plastic, paper, metal, glass, organic, textile`.

| Split | Images | Plastic | Paper | Metal | Glass | Organic | Textile | Empty-label images |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | 13,341 | 8,888 | 7,185 | 4,767 | 6,103 | 35,509 | 827 | 16 |
| Validation | 1,745 | 1,182 | 1,014 | 512 | 850 | 4,830 | 160 | 1 |
| Test (sealed) | 1,769 | 1,309 | 870 | 638 | 892 | 5,029 | 177 | 1 |
| **Total** | **16,855** | **11,379** | **9,069** | **5,917** | **7,845** | **45,368** | **1,164** | **18** |

The 18 empty annotation files are intentional negative images carried from the source data. Every retained object annotation is mapped to the six-class taxonomy; v7 generation checks that source manifest categories and remapped label IDs agree. The final manifest SHA-256 is `a92e916ae3f9019ffb52cd20fea48defabae20c8b52cf8a22f4e7b4c954983b7`; source manifest SHA-256 is `aee7cb8cf3ee59fd7d034230dcf1329f7d34c08df4f3b3646367faa867171bed`.

Split source image counts (train / val / test): TACO ODbL 192 / 26 / 24; KNR-PET-7 4,080 / 527 / 539; Roboflow Garbage Classification 3 v2 8,347 / 1,045 / 1,047; MRS Textile-only 722 / 147 / 159. Dataset and manifests are local under ignored `datasets/`; upload `datasets/multiclass_final_v7/` as a Kaggle Dataset before running the notebook. The YAML uses `path: .` and relative split paths.

## Data and visual review

Visual artifacts inspected: a source/class contact sheet covering each observed source/class combination (TACO, KNR-PET-7, Roboflow Garbage Classification 3 v2, and MRS Textile-only), plus the focused Roboflow and MRS sheets and KNR bottle sample. The visible boxes generally align with the labeled object, but source semantics limit what this model can claim:

- Roboflow `biodegradable` includes whole fruit and produce; it is broad organic recognition, not a banana-peel benchmark.
- MRS `Textile` includes plush toys, pillows, and fabric household objects as well as garments. Do not promise that every detected textile item is discarded clothing.
- Sources are international; they do not establish Vietnam-specific performance. Collect a separate, permissioned Vietnamese field evaluation set before making local accuracy claims.
- Sampling is visual QA, not a manual reannotation of all 80,742 retained boxes. Small, occluded, or ambiguous annotations can remain.

The full audit output is committed at `ml/reports/multiclass_final_v7_audit.json` and also recorded beside the ignored local dataset at `datasets/multiclass_final_v7/audit_report.json`. It reports 16,855 decoded images, 0 decode/missing-label/invalid-box/hash errors, 0 exact duplicate pairs, 0 cross-split source-group leaks, and 0 foreground pHash-distance-4 candidates. Full-frame dHash surfaced 13,037 candidates from common studio backgrounds and is treated as a coarse screen only; foreground-crop pHash was visually reviewed and then used for the near-duplicate gate. Re-run before uploading with:

```powershell
.\.venv\Scripts\python.exe ml\scripts\audit_multiclass_final.py --root datasets\multiclass_final_v7
```

**Do not upload or train if this command fails.** It checks every image can be decoded, every image has an annotation file, finite in-bounds YOLO coordinates and class IDs, consistency across YAML/taxonomy/manifest, image hashes, exact/group leakage, and near-duplicate candidates across splits. It reports per-split class and source counts.

## Training and model selection policy

- Initialization: `yolo26s.pt`, SHA-256 `646f8bc3fe0a656803d95c294f7852321748cb29d13466a1af8862e2db384a1b`.
- Runtime: `ultralytics==8.4.210`; declared ranges are `pillow>=10,<14`, `pyyaml>=6,<7`. The local CPU environment used for this review is Python 3.11, PyTorch `2.15.0+cpu`, Ultralytics `8.4.210`, Pillow `13.0.0`, and PyYAML `6.0.3`. Kaggle's CUDA-enabled PyTorch is retained and its exact version/CUDA runtime is printed into the run manifest. Do not upgrade PyTorch in the notebook.
- One planned run: 50 epochs, 640 px, global batch 8 on one usable GPU or 16 across two T4s, seed 42, deterministic mode, Ultralytics `optimizer=auto`, AMP on, patience 15, close mosaic at epoch 10, two dataloader workers. The 50-epoch budget provides margin under Kaggle's session limit while retaining early stopping. No class reweighting or synthetic labels are introduced.
- Kaggle runner detects available CUDA devices and usable VRAM. Two T4s use DDP `[0, 1]`; one usable CUDA GPU uses `0`; no CUDA stops. The runner attempts the short DDP smoke before full training. A failed dual-GPU smoke only falls back after the explicit `WASTEWISE_ALLOW_SINGLE_GPU_FALLBACK=1` setting and a successful fresh one-GPU smoke. Device configuration does not change during a full run.
- Kaggle mounts the uploaded dataset under `/kaggle/input`, where the dataset's portable `data.yaml` has `path: .`. The runner writes `/kaggle/working/runtime_data.yaml` with the resolved mount root as an absolute path, then verifies it with Ultralytics `check_det_dataset(autodownload=False)` before any GPU smoke. The same runtime YAML is passed to smoke, full training, resume, and validation.
- Preflight acceptance: all six classes present in train/val/test; no audit failures; exact initial checkpoint and package versions match; GPU has at least 8 GiB free; short one-epoch, 1% data smoke finishes. Full training does not begin before these checks.
- Review the saved validation per-class precision, recall, mAP50, and mAP50:95, confusion matrix, PR curves, and prediction plots. Deployment gate: each enabled class must reach validation precision and recall >=0.50, mAP50 >=0.50, and mAP50:95 >=0.25, plus manual review of representative predictions for every class (especially Organic, Textile, Glass, Plastic/Paper/Metal). Do not use overall mAP alone or tune against test. If a class fails, keep it disabled; do not hide it inside the aggregate score. After the model is frozen, evaluate the sealed test exactly once and keep the result separate from training/model selection.

## CPU and integration verification

Local final-taxonomy CPU smoke executed: YOLO26n, one epoch, 96 px, batch 2, 12 train and 12 validation images (two images per class in each split). The run produced `best.pt` and `last.pt`, preserved the expected six class names/order, and completed validation (mAP50 0.0442 on this tiny subset). This score is smoke evidence only and is not a quality estimate. The checkpoint passed `scripts/install_model.py` manifest/checksum validation and installed into a temporary directory. `RealYOLODetector` loaded it; `/api/v1/health` returned `ready`; `/api/v1/scans` returned HTTP 200 with valid boxes, class/category IDs, confidence values, and disposal guidance. That API smoke used confidence 0.001 to exercise detections, so its 296 boxes include false positives and are not a model-quality result. Full pytest suite and frontend production build results are recorded below after completion.

The checked-in local dataset YAML is `ml/config/multiclass_final_v7.yaml`; the dataset upload contains its own portable `data.yaml` (`path: .`). The documented CPU smoke command is:

```powershell
.\.venv\Scripts\python.exe ml\scripts\train_multiclass.py --data datasets\multiclass_final_v7\data.yaml --model yolo26n.pt --name final-six-class-smoke --project outputs\cpu_smoke_final --epochs 1 --batch 2 --imgsz 96 --device cpu --workers 0 --min-free-gb 1 --patience 1
```

Full local pytest suite: **44 passed, 1 Starlette/httpx deprecation warning**. Frontend production build: **passed** (`tsc -b && vite build`). API integration with a real local smoke checkpoint passed. Frontend source supports multiple detections and user corrections; browser interaction with a trained checkpoint has not been verified in this review. Kaggle-specific CUDA, VRAM, one/two-GPU smoke, saved-output persistence, and full training were not run locally.

## Kaggle, persistence, and resume

Open `ml/notebooks/wastewise_final_kaggle.ipynb`, attach the uploaded `multiclass_final_v7` dataset, enable GPU and Internet, and run all cells. The notebook pins `REVIEWED_COMMIT` to the code-bearing hotfix commit; the following notebook-only commit records that pin. The runner saves epoch checkpoints (`save_period=1`) to `/kaggle/working/wastewise_runs/`, validation output, manifest, audit summary, ZIP export, and `SHA256SUMS.txt` under `/kaggle/working/wastewise_artifacts/`.

`/kaggle/working` is temporary. It survives neither an un-saved runtime termination nor a lost session. Kaggle documents 12-hour notebook sessions and a 20 GB saved-output limit. After a run (or before ending a session), use Kaggle **Save Version** and include notebook output; only then is recovery/export from that saved notebook output available. This persistence mechanism has not been exercised in this review, so do not assume that an unsaved interrupted run can be recovered. To resume, attach a saved output containing the complete run directory and set `WASTEWISE_RESUME_RUN` to its directory. Resume is blocked unless the dataset manifest SHA, taxonomy, class order, initial weights SHA, training settings, and GPU device list match the saved `run_config.json`. A saved `last.pt` is required. Ultralytics supports device lists for multi-GPU DDP and checkpoint resume; the notebook verifies actual DDP behavior with a smoke run before full training.

## Install, rollback, and preserved baseline

After verifying `SHA256SUMS.txt`, extract `best.pt` with its adjacent `model_manifest.json`, then run:

```powershell
.\.venv\Scripts\python.exe scripts\install_model.py --checkpoint <extracted>\best.pt --manifest <extracted>\model_manifest.json --weights-dir weights\models
```

Set `DETECTOR_MODE=real`, `MODEL_PATH=weights/models/<model_id>/best.pt`, and `INFERENCE_DEVICE=cpu` in `.env`, then restart the API and verify `/api/v1/health` and `/api/v1/scans` with a multi-object image. Rollback: restore the prior model's `MODEL_PATH` and `DETECTOR_MODE` values, then restart. Model installations are versioned and never overwrite an existing model directory. The SWiM3 three-class baseline, Knowledge Base, and frontend remain in the repository; cigarette litter remains available for manual guidance.

## Remaining ML limits

No training metric yet demonstrates production quality. Organic and Textile are broad source categories; small objects may be missed; there is no Vietnam-specific held-out set; no test-set result is available; source annotations have only sampled visual review; DDP and VRAM are unverified until Kaggle. A single full run may still produce weak per-class metrics. Do not claim reliable banana-peel, old-clothes, or cigarette-butt recognition from this dataset.
