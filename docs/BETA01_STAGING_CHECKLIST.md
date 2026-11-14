# Beta01 staging Go/No-Go checklist

Record date, branch SHA, Docker image ID/digest, model ID, manifest SHA-256, API origin, frontend origin, operator, and rollback image/model/env locations in the staging change record. Do not paste secrets or the checkpoint into this document.

## Before traffic

- [ ] Confirm the branch SHA is the reviewed `feat/soicterra-v3-frontend` preparation commit or its approved successor; no training, curated KB, or feature-scope changes are included.
- [ ] Obtain `best.pt` and `model_manifest.json` from the model owner. Review provenance and run `scripts/install_model.py`; SHA-256, taxonomy version, ordered contiguous class IDs, supported categories, and names pass. Record the checksum and model ID. No legacy-manifest override.
- [ ] Build the CPU image and confirm only the intended files are in the build context; model and env are external read-only/protected artifacts. Confirm UID 10001 can read the mounted pair.
- [ ] Set real mode, CPU, one worker, one container instance, initial inference cap 1, exact CORS origin, and body-size proxy cap. Bind backend port to loopback behind HTTPS. Configure gateway per-client limits if needed; record proxy IP/header assumptions.
- [ ] Wait through checkpoint hash/load and cold start. `health` answers 200, `model_status=ready`, and `/ready` answers 200 with `mode=real`. Treat health alone as liveness.
- [ ] Run `scripts/staging_smoke.py` with a representative image and object-containing ROI through the public API hostname. It reports non-empty real AI detections for both routes and a positive KB catalog count.
- [ ] Check browser calls from the Vercel origin: KB, chatbot fallback/provider as configured, scan, ROI, news, and clear retry guidance on 429/503. Confirm HTTPS, CORS, upload rejection, and that no `GROQ_API_KEY` appears in frontend variables or bundle.
- [ ] Force or simulate news source failure; cached/empty news state does not stop scanning. Confirm KB and chat fallback remain useful if YOLO or Groq is unavailable.
- [ ] Check container logs, CPU/memory, startup time, first-scan latency, 4xx/5xx rates, and reverse-proxy status codes. Save previous image/model/env for rollback and rehearse restart.

## Decision

**GO** only when every required check passes with the actual external checkpoint and the public HTTPS API. **NO-GO** for demo mode, missing/invalid manifest, wrong SHA/taxonomy/class map, `/ready` 503, smoke failure, broken KB/chat fallback, broken CORS, unsupported upload exposure, or missing rollback artifacts. Document any failure and keep staging traffic closed until corrected; rerun the full smoke test after changes.

Preparation tests are recorded in the accompanying commit/hand-off. They do not substitute for checkpoint and host validation.
