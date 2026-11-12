#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DATA="${DATA:-datasets/multiclass_v3/data.yaml}"
MODEL="${MODEL:-yolo26s.pt}"
NAME="${NAME:-wastewise_vietnam_multiclass_v3}"
PROJECT="${PROJECT:-runs/multiclass}"
DEVICE="${DEVICE:-0}"
EPOCHS="${EPOCHS:-80}"
BATCH="${BATCH:-8}"
IMGSZ="${IMGSZ:-640}"
WORKERS="${WORKERS:-4}"
SEED="${SEED:-42}"
PATIENCE="${PATIENCE:-15}"
MIN_FREE_GB="${MIN_FREE_GB:-20}"
RESUME_FROM="${RESUME_FROM:-}"

"$ROOT/scripts/vast_preflight.sh"
args=(--data "$DATA" --model "$MODEL" --name "$NAME" --project "$PROJECT"
      --epochs "$EPOCHS" --batch "$BATCH" --imgsz "$IMGSZ" --device "$DEVICE"
      --workers "$WORKERS" --seed "$SEED" --patience "$PATIENCE" --min-free-gb "$MIN_FREE_GB")
if [[ -n "$RESUME_FROM" ]]; then
  [[ -f "$RESUME_FROM" ]] || { echo "Resume checkpoint not found: $RESUME_FROM" >&2; exit 2; }
  args+=(--resume-from "$RESUME_FROM")
fi
mkdir -p outputs/multiclass
log_path="outputs/multiclass/${NAME}.log"
python ml/scripts/train_multiclass.py "${args[@]}" 2>&1 | tee "$log_path"

RUN_DIR="$PROJECT/$NAME"
[[ -f "$RUN_DIR/weights/best.pt" && -f "$RUN_DIR/weights/last.pt" && -f "$RUN_DIR/model_manifest.json" ]] || {
  echo "Training artifact set incomplete: $RUN_DIR" >&2; exit 3;
}
shopt -s nullglob
plot_files=("$PROJECT/$NAME"/*.png "$PROJECT/$NAME"/*.jpg
            "$PROJECT/${NAME}-validation"/*.png "$PROJECT/${NAME}-validation"/*.jpg)
plot_relative=()
for plot in "${plot_files[@]}"; do plot_relative+=("${plot#"$PROJECT/"}"); done
tar_path="outputs/multiclass/${NAME}.tar.gz"
tar -czf "$tar_path" -C "$PROJECT" "$NAME/weights/best.pt" "$NAME/weights/last.pt" "$NAME/weights/model_manifest.json" \
  "$NAME/run_config.json" "$NAME/model_manifest.json" "$NAME/args.yaml" "$NAME/results.csv" \
  "${plot_relative[@]}" \
  -C "$ROOT/outputs/multiclass" "${NAME}.log"
sha256sum "$tar_path" > "${tar_path}.sha256"
printf 'Training artifact ready: %s\n' "$tar_path"
printf 'Training log: %s\n' "$log_path"
printf 'SHA-256: %s\n' "$(cut -d' ' -f1 "${tar_path}.sha256")"
printf 'Validation only; test split was not evaluated.\n'
if [[ -n "${ARTIFACT_REMOTE:-}" ]]; then
  command -v rsync >/dev/null || { echo 'ARTIFACT_REMOTE set but rsync is unavailable' >&2; exit 4; }
  rsync -av --partial --progress "$tar_path" "${tar_path}.sha256" "$ARTIFACT_REMOTE"
fi
echo 'Stop the Vast.ai instance in the dashboard after verifying the artifact copy.'
