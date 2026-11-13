# YOLO26 training and deployment on Vast.ai

This procedure uses the seven-class `multiclass_v5` dataset: audited v4 plus 1,041 Textile-only images from MRS Trash Detection. It preserves SWiM3, v4, v3, and v2. Local preflight checks do not start training; start the paid GPU session only when ready.

## What to transfer

The audited dataset is `datasets/multiclass_v5/` (16,923 images and 80,886 boxes), and the initialization checkpoint is `yolo26s.pt`. Classes, in model order, are `plastic`, `paper`, `metal`, `glass`, `organic`, `textile`, `cigarette_litter`. `datasets/` is git-ignored, so transfer the built v5 folder explicitly; a Git clone alone will not contain it. Transfer the repository revision containing this runbook and scripts as well. The manifest retains per-image source, license, hashes, source classes, and mapping. Preserve CC BY 4.0 attribution for KNR-PET-7 and Roboflow, Apache 2.0 terms for MRS, and follow the ODbL-marked TACO image terms.

Example from a local shell after the GPU instance is reachable over SSH:

```bash
REMOTE=root@YOUR_VAST_SSH_HOST
VAST_PORT=YOUR_VAST_SSH_PORT
ssh -p "$VAST_PORT" "$REMOTE" 'mkdir -p ~/wastewise/datasets ~/wastewise/weights'
rsync -av --partial --progress -e "ssh -p $VAST_PORT" datasets/multiclass_v5/ "$REMOTE:~/wastewise/datasets/multiclass_v5/"
rsync -av --partial --progress -e "ssh -p $VAST_PORT" yolo26s.pt "$REMOTE:~/wastewise/weights/yolo26s.pt"
```

Replace the example SSH target and port with the host details shown by Vast.ai. Clone or upload the project source to `~/wastewise` before running commands. For a pushed revision, `git clone https://github.com/ducnguyenhuu26/Project1.git ~/wastewise` is sufficient; otherwise upload the exact local source revision.

## Prepare and preflight

Use an instance with a working NVIDIA driver, CUDA PyTorch, at least 16 GiB available host RAM, 12 GiB VRAM, and 20 GiB free disk. The run uses YOLO26s at 640 pixels and batch 8 by default; if training runs out of memory, start a fresh uniquely named run with a lower batch. Resume an interrupted run with its original configuration.

```bash
cd ~/wastewise
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export DATA="$PWD/datasets/multiclass_v5/data.yaml"
export MODEL="$PWD/weights/yolo26s.pt"
export NAME="wastewise-vietnam-multisource-yolo26s-v5"
export PROJECT="$PWD/runs/multiclass"
export DEVICE=0 EPOCHS=80 BATCH=8 IMGSZ=640 WORKERS=4 SEED=42 PATIENCE=15 MIN_FREE_GB=20 MIN_RAM_GB=16 MIN_VRAM_GB=12
bash scripts/vast_preflight.sh
```

Preflight verifies CUDA, the dataset labels/splits, free disk, taxonomy version, and SHA-256 hashes. It exits without training. Resolve any `PREFLIGHT BLOCKED` result before starting the paid session.

## Train and preserve artifacts

```bash
bash scripts/vast_train.sh
```

Training uses the train split and validates against `val`; it does not evaluate `test`. The run writes `best.pt`, `last.pt`, `model_manifest.json`, `run_config.json`, `results.csv`, `args.yaml`, validation plots, and a console log, then packages them under `outputs/multiclass/`. Monitor from a second SSH session with `tail -f ~/wastewise/outputs/multiclass/$NAME.log`. Copy the `.tar.gz` and `.sha256` off the GPU instance and verify the hash before stopping the instance. Set `ARTIFACT_REMOTE=user@host:/path/` before launch if an rsync destination is configured and reachable.

The test split is reserved for a later frozen evaluation after model selection. Do not use it to choose epochs, confidence, or class mappings.

## Resume an interrupted run

Keep the original `NAME`, `PROJECT`, and `DATA`. Set `RESUME_FROM` to that run's `weights/last.pt` and rerun both preflight and training:

```bash
export RESUME_FROM="$PROJECT/$NAME/weights/last.pt"
bash scripts/vast_preflight.sh
bash scripts/vast_train.sh
```

The script rejects a resume when its run directory, dataset YAML, or taxonomy version differs.

## Install and serve the selected checkpoint

On the deployment checkout, extract the artifact and install into a new versioned directory. Existing model versions are never replaced. The installed model manifest must show the seven v5 classes and taxonomy `2026-11-13.2` before enabling real inference.

```bash
mkdir -p imported-model
tar -xzf wastewise-vietnam-multisource-yolo26s-v5.tar.gz -C imported-model
python scripts/install_model.py \
  --checkpoint imported-model/wastewise-vietnam-multisource-yolo26s-v5/weights/best.pt \
  --manifest imported-model/wastewise-vietnam-multisource-yolo26s-v5/weights/model_manifest.json
```

Set the printed `MODEL_PATH` plus `DETECTOR_MODE=real` and `INFERENCE_DEVICE=cpu` in `.env`, then restart the FastAPI service. Confirm `/api/v1/health` returns `model_status: ready` and seven `supported_category_ids`; upload a test image through the frontend and verify the response taxonomy version and class names. Keep the prior `.env` and model directory for rollback.

## Data and model limitations

The new sources are not Vietnam-specific, and the audit includes sampled visual checks rather than manual reannotation of all boxes. `biodegradable` maps to `organic` and includes ordinary produce; it does not teach the detector whether an item is discarded or establish banana-peel performance. MRS `Textile` includes plush toys, pillows and fabric household objects as well as clothes, so it is not a discarded-jacket benchmark. `cigarette_litter` remains a small class (18/2/3 images in train/validation/test). The held-out test remains untouched until model selection is frozen. This dataset is a ready, auditable training input, not evidence of production quality or Vietnam-specific accuracy. Retain source attribution and license terms in any model artifact.
