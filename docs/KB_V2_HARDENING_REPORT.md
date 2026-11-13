# SOICTERRA Knowledge Base v2 hardening report

## Root causes fixed

- `backend/recommendations.py`: generic reuse and contamination rules were mixed with object-specific rules. A damaged glass bottle could retain intact-container advice, and any `special_collection` object marked usable could be moved into reuse. The engine now applies an explicit safety-first order, limits reuse to eligible objects, requires conservative guidance for uncertain glass, contamination and battery states, and keeps the final stream/rationale aligned. The KB and taxonomy are validated at import for duplicate IDs, categories, streams, question/option references and empty guidance.
- `backend/recommendation_kb.json`: battery condition combined active thermal incidents with other damage, so it could not give appropriately different guidance. The question now separates active heat/fire, damage, unknown and normal states. Glass bottle/jar records ask whether a sharp edge is exposed. Aerosol, battery and needle guidance now states key safety limits.
- `backend/recommendation_api.py`: catalog responses did not expose a stable total for the UI. It now returns `total_count`; invalid provenance categories and rule inputs return 422, while unknown objects remain 404.
- `frontend/src/components/RecommendationWizard.tsx`: catalog/detail requests were abortable but evaluate requests were not. A late response could replace guidance after the object or answers changed. Evaluation now has abort and request-identity guards; errors are isolated by operation; changed answers, object, scan or detector context clears stale output. The selected object remains visible when search/filter results change. Catalog size comes from the API, and the manual wizard renders even if the legacy materials endpoint is unavailable.
- `frontend/src/components/ScanStudio.tsx`: `.find()` attributed a shared material class to the first matching detection. Provenance is now attached only when one non-excluded detection unambiguously matches; otherwise the source is manual. A correction carries the original `d.category_id`, and the UI identifies it as an unverified YOLO hint.
- `tests/test_api.py`: a machine-local `.env` model path made the existing device configuration test fail. The test now sets its own model path and does not depend on installed weights.

## Changed files

- `backend/recommendations.py`
- `backend/recommendation_api.py`
- `backend/recommendation_kb.json`
- `frontend/src/components/RecommendationWizard.tsx`
- `frontend/src/components/ScanStudio.tsx`
- `frontend/src/components/KnowledgeSections.tsx`
- `frontend/src/main.tsx`
- `frontend/src/recommendations.css`
- `tests/test_recommendations.py`
- `tests/test_api.py`
- `docs/KB_V2_HARDENING_REPORT.md`

## Automated checks

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Result: **203 passed**, one Starlette deprecation warning about its current `httpx` TestClient integration. No test required `best.pt`, a network service or paid inference. KB-specific coverage includes 70 distinct object/state scenarios, every one of the 43 KB records, validator mutation cases, and endpoint happy, pending, error and provenance cases.

Run from `frontend`:

```powershell
npm run build
```

Result: **passed**. The script runs `tsc -b` and Vite 7.3.8; 1,596 modules transformed. `package.json` has no lint or frontend test script, and no frontend test framework is installed.

Whitespace validation:

```powershell
git diff --check
```

Result: passed. Git printed only its LF-to-CRLF working-copy notices.

## Manual browser scenarios

1. Open the Library without uploading an image. Search `urgo`, select the release liner, answer both questions, and verify the result remains residual/conditional and does not call it curbside paper recycling.
2. Search for `chai nhựa`; compare clean, food-contaminated, unknown and hazardous answers. Hazardous contamination must not return cleaning/recycling instructions.
3. In Scan Studio, use a single textile detection, correct its group to paper, select a paper object and inspect the evaluate request/result: `source=corrected`, `detected_category_id=textile`, and advice for the explicitly selected paper object. The page should label the YOLO class as a hint.
4. With browser network throttling enabled, submit an evaluation, change the selected object or an answer before the response returns, and verify the old response does not appear under the new state.
5. Check a damaged glass bottle with and without an exposed sharp edge, a damaged battery, and a pressurized aerosol. Verify the safety guidance and warnings.
6. Repeat the object search on a narrow mobile viewport and verify the controls/results remain usable.

## Remaining review

All 43 records remain draft general guidance. Their local collection routes and legal handling details have not been verified against authoritative, location-specific sources; `local_collection_verified` remains `false`. Have a qualified reviewer verify safety and local wording before presenting this as official disposal policy. No merge or deployment was performed.
