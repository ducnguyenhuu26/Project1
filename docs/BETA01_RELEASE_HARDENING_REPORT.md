# Beta 01 release hardening report

**Branch:** `feat/soicterra-v3-frontend`  
**Starting HEAD:** `e0a08df747b882e1bc47e1d441d7e5333f95e204` (`Update Beta version 01`)  
**Scope:** hardening P0 and P1 behavior without changing the CV–KB design or adding model classes.

## Confirmed issues and fixes

### P0 — request and model readiness

- **Unbounded scan/ROI admission was confirmed by route inspection.** Both endpoints could submit work to the shared thread pool with no API-level cap. They now share a nonblocking process-local inference semaphore (default two slots) that covers upload decode, crop and prediction. Saturation returns `503 INFERENCE_BUSY` and `Retry-After: 2`; the frontend displays the server's retry guidance and keeps KB lookup available.
- **A real checkpoint without a manifest was accepted as the legacy three-class map.** A missing manifest now fails readiness in real mode. An operator can explicitly enable `ALLOW_LEGACY_MODEL_MANIFEST=true` for a reviewed legacy checkpoint. Real manifests must match taxonomy and supported class IDs, include a SHA-256 for the checkpoint, and match that hash; class names and checkpoint load errors leave the detector not ready. No fallback to demo occurs.
- **Chat and manual news refresh had no endpoint throttling.** Chat is limited to 10 requests per client per rolling 60 seconds; forced news refresh is limited to one request per client per 60 seconds. Responses return `429 RATE_LIMITED` with `Retry-After`. Client identity uses the direct socket peer, not untrusted `X-Forwarded-For`.
- **Request payload protections were reviewed.** Existing image handling enforces JPEG/PNG/WebP, 10 MB upload size, 24 megapixels, image decoding, and ROI bounds/minimum dimensions; the image pixel cap is checked before RGB conversion. CORS origins are trimmed and `Retry-After` is exposed to browser clients.

### P1 — detections, advice and client state

- **Repeated ROI results could duplicate an existing object.** A reproduced overlapping same-category AI result is now suppressed at IoU ≥ 0.5 when provenance matches. Different classes or sources remain separate; existing IDs and sessions are preserved. ROI summary counts are based on accepted new detections.
- **Corrections were not obvious in the result card and counts could go stale.** Cards now show the corrected class while preserving the original YOLO label and confidence. The visible summary is recomputed from current detections, corrections, exclusions and manual labels.
- **Manual recommendation state could survive into a new scan.** It is now keyed to the scan ID, like per-object sessions. Existing scan versioning and abort behavior were checked for image replacement, scan reruns and ROI cancellation; recommendation evaluation already uses request IDs and abort controllers. Regression coverage was added for manual session isolation.
- **Chat source text overstated KB grounding, and safety-critical answers depended on the provider.** The footer now explains that the assistant may use general knowledge and that each answer identifies its source. Questions mentioning swollen/hot/smoking batteries, sharps, chemicals, or smoke/fire receive fixed safety guidance without calling Groq. Prompt history is bounded to 3,500 characters, Groq timeout/fallback behavior remains in place, and rate-limit errors are surfaced to the user.
- **News resilience:** existing cached snapshots remain in use when feed refresh fails; forced refresh throttling now protects the RSS path without blocking scan admission.

## Tests and build

Final verification on the completed code state:

- Backend: `356 passed` in 222.17 seconds.
- Frontend tests: 18 passed.
- Production build: `npm run build` succeeded (TypeScript and Vite).
- `git diff --check`: clean.
- Backend emitted one existing Starlette deprecation warning about using `httpx` with `TestClient`; tests passed.

Focused backend regression coverage includes missing/invalid manifests, missing and mismatched checkpoint hashes, checkpoint-load and class-name errors, shared scan/ROI admission, chat/news throttling, forwarded-header spoofing, hazardous-chat fallback, prompt budget and injection framing. Frontend regression coverage includes ROI deduplication, preserving distinct classes, corrected-label provenance and manual-session lifetime.

## Remaining risks and staging checklist

- Admission and request throttles are in-memory per worker. Multi-worker or multi-instance deployments need a trusted gateway/shared limiter for service-wide limits; configure trusted proxy handling before consuming forwarded client IP headers.
- A real production checkpoint was not loaded in this hardening run. Before staging, use the intended installed checkpoint/manifest pair, verify `/api/v1/health` reports `ready`, and smoke-test scan plus ROI with representative images. No training was run.
- The safety response matcher covers explicit high-risk terms and cannot replace local emergency, medical, chemical or waste-authority instructions. Collection availability remains unverified; the UI does not claim a local collection point has been confirmed.
- The deterministic chat answer for unmatched topics remains a fallback if Groq is unavailable; provider availability and rate limits remain external dependencies.
- Before release, verify allowed CORS origins, `MAX_UPLOAD_MB`, `MAX_CONCURRENT_INFERENCES`, and the default-disabled legacy-manifest switch in the target environment. No deployment was performed.
