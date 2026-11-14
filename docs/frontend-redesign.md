# WasteWise VN frontend redesign

## Design and structure

The redesign uses a midnight green, bone, and muted sage palette with restrained brass details, editorial Vietnamese typography, precise field labels, and a dark/light rhythm. The Hanoi street illustration in `frontend/public/urban-ecology.svg` is original vector artwork made for this project; object outlines are explicitly marked as vector illustration. No third-party campaign artwork or runtime image CDN is used. Google Fonts (Be Vietnam Pro and Manrope) have system fallbacks.

The React entry point now composes `SiteHeader`, `Hero`, `ScanStudio`, `KnowledgeSections`, `PrivacyHistory`, `SiteFooter`, and `ChatAssistant`. Shared FastAPI response types live in `frontend/src/types.ts`; `frontend/src/lib/api.ts` owns typed fetch requests, multipart upload, and status-aware error messages. Styling remains in one focused stylesheet because the application is small and shares design tokens and responsive rules throughout.

## API integrity and behavior

- The current API includes health, waste types, multipart scan `image`, region rescan `image` + `x1/y1/x2/y2`, and chat message/history/category fields. See [the Beta01 integration report](CV_KB_INTEGRATION_REPORT.md) for the current contracts.
- Health and scan `supported_category_ids` drive the supported-category labels. The real/demo mode, model version, taxonomy version, confidence, warnings, dimensions, individual detections, and advice remain visible where applicable. Demo scans are labeled as illustrations and do not imply confidence scores.
- Image selection accepts JPEG, PNG, and WebP up to 10 MB. API errors retain FastAPI's detail when available and provide useful fallbacks for 413, 415, 422, and 503. Network errors and the 60-second timeout are shown in the scan panel.
- Each detection retains its own correction and exclusion control. The overlay uses the API's EXIF-corrected dimensions and scales the SVG viewBox with the displayed image's natural aspect ratio. No-detection real scans lead into manual lookup.
- Advice is from the knowledge endpoint; model coverage is not inferred from the library alone when health or scan data is available. Chat calls Groq for every question when configured, optionally adding matching KB context; model outage or missing key triggers the KB fallback. Local scan history stores only timestamps and material IDs in `localStorage`; uploaded image bytes are not included in that history.
- Keyboard focus, native buttons and selects, an accessible mobile menu, status/error announcements, semantic headings, reduced-motion handling, and narrow-screen layouts are included.

## Verification

- `npm ci` in the active frontend directory was blocked because Windows refused to unlink the running Vite server's `esbuild.exe` (`EPERM`). A non-destructive `npm install --ignore-scripts --no-audit --no-fund` restored its missing command shims without changing the lockfile. To verify the clean install, I copied the tracked frontend inputs to an isolated temporary directory: `npm ci` succeeded there with 0 vulnerabilities and `npm run build` passed (`tsc -b && vite build`). The in-repository `npm run build` also passed.
- `python -m pytest -q` with the system Python could not collect the suite because that interpreter lacks FastAPI and Ultralytics. Running the same command with `.venv\Scripts\python.exe` passed: **44 passed**, with one Starlette/httpx deprecation warning.
- Browser QA was performed on the running local frontend at mobile (390 px), tablet (768 px), and desktop (1440 px). At 390 px, the document was 375 CSS px wide in a 390 px browser viewport, so it did not overflow. At 768 px the original two-column hero wrapped too tightly, so a tablet stacking breakpoint was added and visually re-inspected. The bundled demo API returned three illustration detections, taxonomy/model metadata, and advice. Per-object correction changed only the selected first detection to glass; excluding it reduced detection boxes and rows from three to two. No screenshot file was saved.
- Manual checklist: choose/drop a valid image; reject wrong MIME and >10 MB files; confirm timeout/network feedback; confirm 413/415/422/503 messages; confirm no-detection fallback; compare overlays at mobile/tablet/desktop; correct and exclude different objects; add a manual material; expand a library item; search/filter the library; ask a context-aware chat question; clear local history; keyboard through menu, upload, scan controls, library, and chat; enable reduced motion.

## Run locally

Start the API from the repository root with `uvicorn backend.main:app --reload --port 8000`, then start the frontend with `cd frontend && npm run dev`. Vite proxies `/api` to `http://127.0.0.1:8000`; set `VITE_API_URL` when using another API origin.

The current detector can be in demo mode or use an available real checkpoint. Real inference coverage is determined by the live API; the interface does not claim that future or unready classes are already deployed.
