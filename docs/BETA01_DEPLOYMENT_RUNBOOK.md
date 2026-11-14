# SOICTERRA Beta01 staging deployment

This prepares the FastAPI backend and Vercel frontend on `feat/soicterra-v3-frontend` at or after `ebdadd2`. It does not supply a model or perform deployment. Use the release checklist alongside this runbook.

## Artifacts and trust boundary

The CPU image uses Python 3.11, pinned direct production packages, CPU PyTorch wheels, a non-root UID, and exactly one Uvicorn worker. Its build context includes only `backend/`, `requirements-production.txt`, and `Dockerfile`; `.dockerignore` excludes weights, datasets, local files, `.env`, and keys. Transitive dependencies resolve at build time: retain the built image digest for exact rollback, and rebuild/retest deliberately when updating dependencies. The image has no model. Mount the checkpoint and its manifest read-only at `/models`.

Use a separately supplied, reviewed `best.pt` with `model_manifest.json` from the same training run. Do not create a manifest by guessing class labels or a hash. The manifest requires `schema_version: "1.0"`, `task: "detect"`, `model_family: "YOLO26"`, a matching `taxonomy_version`, a unique `model_id`, `checkpoint_sha256`, and an ordered `class_map` from class ID 0. `scripts/install_model.py` checks the SHA-256, taxonomy, supported categories, class IDs, and taxonomy model names; the API checks hash, manifest/class IDs, and the class names loaded from the actual checkpoint. Keep `ALLOW_LEGACY_MODEL_MANIFEST=false`. Inspect the manifest and checkpoint provenance with the model owner before go-live.

## Local Docker staging rehearsal

Run these from the repository root after placing the supplied pair in a private directory outside the repository. Replace the example paths and origins. The sample image must contain a supported object; set ROI coordinates in original image pixels around that object.

```powershell
$ModelSource = 'C:\private\soicterra-model'
$Installed = 'C:\private\soicterra-installed'
New-Item -ItemType Directory -Force $Installed | Out-Null
& .\.venv\Scripts\python.exe scripts/install_model.py --checkpoint "$ModelSource\best.pt" --manifest "$ModelSource\model_manifest.json" --weights-dir $Installed
# Record the printed model_id, then use its directory as $ModelDir.
$ModelDir = Join-Path $Installed '<model_id>'
Copy-Item .env.production.example C:\private\soicterra-staging.env
# Edit C:\private\soicterra-staging.env: CORS_ORIGINS must name the exact HTTPS Vercel origin.
docker build -t soicterra-api:beta01 .
docker run -d --name soicterra-api --restart unless-stopped --env-file C:\private\soicterra-staging.env -v "${ModelDir}:/models:ro" -p 127.0.0.1:8000:8000 soicterra-api:beta01
docker logs --tail 100 soicterra-api
& .\.venv\Scripts\python.exe scripts/staging_smoke.py --base-url http://127.0.0.1:8000 --image C:\private\representative.jpg --roi 20 20 300 300 --min-catalog-count 1
```

If no local `.venv` exists, use any Python 3.11+ interpreter for the two standard-library scripts. The installed model directory must be readable by container UID 10001. Do not put it in the Docker build context. `docker inspect soicterra-api --format '{{json .State.Health}}'` checks liveness only.

## Ordinary Linux container host

Install Docker and configure an HTTPS reverse proxy under a dedicated API hostname. Keep the container port bound to loopback. Use your own private directories and permissions; the model needs read access for UID 10001. Do not copy the real `.env` into the repository or image.

```bash
git clone --branch feat/soicterra-v3-frontend https://github.com/ducnguyenhuu26/Project1.git soicterra-beta01
cd soicterra-beta01
git rev-parse HEAD
sudo mkdir -p /srv/soicterra/models /etc/soicterra
sudo python3 scripts/install_model.py --checkpoint /private/incoming/best.pt --manifest /private/incoming/model_manifest.json --weights-dir /srv/soicterra/models
# Use the printed model_id; the installed directory contains best.pt and model_manifest.json.
sudo chown -R root:10001 /srv/soicterra/models/<model_id>
sudo chmod 750 /srv/soicterra/models/<model_id>
sudo chmod 640 /srv/soicterra/models/<model_id>/*
sudo cp .env.production.example /etc/soicterra/api.env
sudoedit /etc/soicterra/api.env
sudo chmod 600 /etc/soicterra/api.env
docker build -t soicterra-api:beta01 .
docker image inspect soicterra-api:beta01 --format '{{.Id}}'
docker run -d --name soicterra-api --restart unless-stopped --env-file /etc/soicterra/api.env --mount type=bind,src=/srv/soicterra/models/<model_id>,dst=/models,readonly -p 127.0.0.1:8000:8000 soicterra-api:beta01
docker logs --tail 100 soicterra-api
python3 scripts/staging_smoke.py --base-url https://api.example.org --image /private/representative.jpg --roi 20 20 300 300 --min-catalog-count 1
```

Set `CORS_ORIGINS=https://your-frontend.vercel.app` in the server env file, without a path or trailing slash. Set `MODEL_PATH=/models/best.pt`, `DETECTOR_MODE=real`, `INFERENCE_DEVICE=cpu`, and start with `MAX_CONCURRENT_INFERENCES=1`. Optional `GROQ_API_KEY` belongs in this protected server env file only. Chat uses the curated KB fallback when the provider is absent. The news cache is bundled as seed data; refresh may fail without blocking scans. The container's read-only news data directory prevents persisting refreshed news across restarts, so expect a refresh after cold start.

Route the API hostname over TLS to `http://127.0.0.1:8000`, preserve the original `Host`, and set a proxy request-body limit consistent with `MAX_UPLOAD_MB` (for example 12 MB for a 10 MB file plus multipart overhead). Restrict direct access to the loopback port. The app's rate limiter keys on the direct socket peer and deliberately ignores untrusted `X-Forwarded-For`; behind a reverse proxy, all clients may therefore share the chat/news throttle unless the gateway enforces its own per-client limits. Do not enable trust for arbitrary forwarded IP headers. If configuring trusted proxy IP processing later, enumerate only the proxy's fixed IPs and test spoofed-header behavior. One worker and one instance keep the in-memory inference semaphore coherent; multiple replicas require a shared admission/rate limiter and capacity review. A saturated scan/ROI returns `503` with `INFERENCE_BUSY` and `Retry-After`; chat/news throttles return `429` with `RATE_LIMITED` and `Retry-After`. Upload type, byte size, pixel count, decoding and ROI bounds remain enforced by the API.

## Probes and operations

`GET /api/v1/health` is process liveness. It returns HTTP 200 even if `model_status` is `missing_checkpoint` or `invalid_manifest`; its demo `ready` state is not production readiness. `GET /api/v1/ready` returns 200 only when a real detector was loaded, otherwise 503. Neither endpoint proves representative inference. The smoke script checks real mode, loaded model, KB catalog total, a real scan with an AI detection, and an ROI scan with an AI detection. Run it after each image/model update and from the public HTTPS hostname. A missing checkpoint should leave KB/catalog and deterministic chat available, with scans returning 503.

The model file is hashed and loaded at startup. CPU cold start can be slow, especially on a small host. Allow several minutes before judging readiness; use liveness start period and external proxy startup timeout accordingly. First inference may be slower due to framework initialization. Do not route public traffic until the smoke script passes. Check memory and CPU during scan and ROI; tune admission only after measuring the target host.

```bash
docker logs --since 10m soicterra-api
docker stats --no-stream soicterra-api
docker inspect soicterra-api --format '{{json .State}}'
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/ready
docker restart soicterra-api
```

Track request counts and status codes in the reverse proxy logs, especially 413, 415, 422, 429, 503, and 5xx; track latency, CPU, memory, container restarts, and `/ready` status. Do not log image bodies, API keys, or uploaded filenames. For rollback, retain the previous image ID, previous external model directory, and previous protected env file. Stop and remove only the staging container, then recreate it with those previous artifacts and the same bind mount/port; rerun the smoke script before restoring traffic:

```bash
docker stop soicterra-api
docker rm soicterra-api
docker run -d --name soicterra-api --restart unless-stopped --env-file /etc/soicterra/api.previous.env --mount type=bind,src=/srv/soicterra/models/<previous_model_id>,dst=/models,readonly -p 127.0.0.1:8000:8000 <previous_image_id>
python3 scripts/staging_smoke.py --base-url https://api.example.org --image /private/representative.jpg --roi 20 20 300 300 --min-catalog-count 1
```

## Vercel frontend

Import the same repository into Vercel with **Root Directory** `frontend`, **Framework** Vite, **Build Command** `npm run build`, **Install Command** `npm ci`, and **Output Directory** `dist`. Set public build variable `VITE_API_URL=https://api.example.org` (origin only, no `/api` path). This value is embedded in the browser bundle; all scan, ROI, KB, chatbot, and news calls use that origin. A trailing slash is trimmed. Vite's local `/api` proxy applies only to local development when the variable is empty. The API must have valid HTTPS and exact frontend origin in `CORS_ORIGINS`; test browser preflight and `Retry-After` visibility. Do not set `GROQ_API_KEY` or any other secret in Vercel frontend variables, and never use a `VITE_` secret. Rebuild the frontend after changing `VITE_API_URL`.

## Preparation verification (2026-11-14)

- Backend: `.venv\Scripts\python.exe -m pytest -q` — **358 passed**, one existing Starlette `httpx` deprecation warning. Focused staging tests: **2 passed**.
- Frontend: `npm test -- --run` — **18 passed**. `npm run build` — **passed**. A second build with `VITE_API_URL=https://api.example.org/` passed and its generated JavaScript contained the HTTPS origin.
- Python compilation for the smoke script and API passed; `pip check` found no broken requirements; `git diff --check` found no whitespace errors.
- Initial verification caught and corrected a TypeScript `ImportMeta.env` type error and a test fixture expecting `TestClient` to translate an uncaught news exception. An initial bundle search used a Windows-incompatible glob; rerunning the origin build with a directory search passed.
- Docker CLI was unavailable here, so the image was **not built or run**. `weights/best.pt` was absent; there was **no real checkpoint, manifest, inference smoke run, or staging deployment**. The go-live checklist remains open until completed on the host with the supplied checkpoint.
