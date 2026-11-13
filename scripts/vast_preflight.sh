#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DATA="${DATA:-datasets/multiclass_v5/data.yaml}"
MODEL="${MODEL:-yolo26s.pt}"
NAME="${NAME:-wastewise_vietnam_multiclass_v5}"
PROJECT="${PROJECT:-runs/multiclass}"
DEVICE="${DEVICE:-0}"
EPOCHS="${EPOCHS:-80}"
BATCH="${BATCH:-8}"
IMGSZ="${IMGSZ:-640}"
WORKERS="${WORKERS:-4}"
SEED="${SEED:-42}"
PATIENCE="${PATIENCE:-15}"
MIN_FREE_GB="${MIN_FREE_GB:-20}"
MIN_RAM_GB="${MIN_RAM_GB:-16}"
MIN_VRAM_GB="${MIN_VRAM_GB:-12}"

fail() { printf 'PREFLIGHT BLOCKED: %s\n' "$*" >&2; exit 2; }
[[ -f "$DATA" ]] || fail "dataset YAML not found: $DATA"
[[ -f "$MODEL" ]] || fail "pretrained checkpoint missing: $MODEL (transfer yolo26s.pt before training)"
project_check="$PROJECT"
while [[ ! -d "$project_check" ]]; do
  parent="$(dirname "$project_check")"
  [[ "$parent" != "$project_check" ]] || fail "no existing parent for project directory: $PROJECT"
  project_check="$parent"
done
[[ -d "$project_check" && -w "$project_check" ]] || fail "no write access to project directory or parent: $project_check"
command -v nvidia-smi >/dev/null || fail "nvidia-smi unavailable; select a CUDA GPU instance"
nvidia-smi >/dev/null || fail "GPU driver is not responding"

MIN_VRAM_GB="$MIN_VRAM_GB" python - <<'PY' || exit 2
import os, torch, ultralytics
if not torch.cuda.is_available():
    raise SystemExit("PREFLIGHT BLOCKED: torch.cuda.is_available() is false")
props = torch.cuda.get_device_properties(0)
print(f"GPU: {props.name}; VRAM: {props.total_memory / 2**30:.1f} GiB")
if props.total_memory < float(os.environ["MIN_VRAM_GB"]) * 2**30:
    raise SystemExit(f"PREFLIGHT BLOCKED: need {os.environ['MIN_VRAM_GB']} GiB VRAM")
print(f"CUDA: {torch.version.cuda}; torch: {torch.__version__}; ultralytics: {ultralytics.__version__}")
PY

free_gb="$(df -Pk . | awk 'NR==2 {printf "%.1f", $4/1024/1024}')"
mem_gb="$(awk '/MemAvailable:/ {printf "%.1f", $2/1024/1024}' /proc/meminfo)"
printf 'Host RAM available: %s GiB (minimum %s); disk available: %s GiB\n' "$mem_gb" "$MIN_RAM_GB" "$free_gb"
awk -v mem="$mem_gb" -v need="$MIN_RAM_GB" 'BEGIN {exit !(mem >= need)}' || fail "need ${MIN_RAM_GB} GiB available host RAM, found ${mem_gb} GiB"
awk -v free="$free_gb" -v need="$MIN_FREE_GB" 'BEGIN {exit !(free >= need)}' || fail "need ${MIN_FREE_GB} GiB free disk, found ${free_gb} GiB"

taxonomy_sha="$(sha256sum backend/taxonomy.json | awk '{print $1}')"
dataset_manifest="${DATA%/data.yaml}/dataset_manifest.json"
[[ -f "$dataset_manifest" ]] || fail "dataset manifest missing: $dataset_manifest"
dataset_sha="$(sha256sum "$dataset_manifest" | awk '{print $1}')"
model_sha="$(sha256sum "$MODEL" | awk '{print $1}')"
printf 'Taxonomy SHA-256: %s\nDataset manifest SHA-256: %s\nPretrained checkpoint SHA-256: %s\n' \
  "$taxonomy_sha" "$dataset_sha" "$model_sha"

args=(--data "$DATA" --model "$MODEL" --name "$NAME" --project "$PROJECT" \
  --epochs "$EPOCHS" --batch "$BATCH" --imgsz "$IMGSZ" --device "$DEVICE" \
  --workers "$WORKERS" --seed "$SEED" --patience "$PATIENCE" \
  --min-free-gb "$MIN_FREE_GB" --preflight-only)
if [[ -n "${RESUME_FROM:-}" ]]; then
  [[ -f "$RESUME_FROM" ]] || fail "resume checkpoint not found: $RESUME_FROM"
  args+=(--resume-from "$RESUME_FROM")
fi
python ml/scripts/train_multiclass.py "${args[@]}"
printf 'PREFLIGHT PASS — no training started.\n'
