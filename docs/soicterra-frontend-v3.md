# SOICTERRA Frontend — V3 Port

The React frontend follows the approved V3 editorial direction: cinematic dark hero, SoICTERRA red identity, ivory story and scan surfaces, gold demo accents, and responsive research/library sections. The V3 reference artwork used for the hero is stored locally in `frontend/public/soicterra-hero.jpg`; no third-party image hotlinks are required. The large decorative detection graphic is identified as illustrative and is not presented as model output.

## Component map

| Page area | React source |
| --- | --- |
| Header, hero, story and purpose | `frontend/src/components/SiteHeader.tsx`, `Hero.tsx`, `StorySection.tsx`, `MissionSection.tsx` |
| Scan Studio and API-backed results | `frontend/src/components/ScanStudio.tsx`, `frontend/src/main.tsx` |
| Technology, waste knowledge and team | `frontend/src/components/TechnologySection.tsx`, `KnowledgeSections.tsx`, `TeamSection.tsx` |
| Closing call to action, footer and assistant | `frontend/src/components/ClosingSection.tsx`, `SiteFooter.tsx`, `ChatAssistant.tsx` |
| Shared visual system and scroll reveal | `frontend/src/style.css`, `frontend/src/lib/useReveal.ts` |

## Editing Vietnamese copy and team profiles

Edit `frontend/src/content/siteContent.ts`. It contains the site descriptor, affiliation/disclaimer, hero, story, mission, technology, library, team and closing copy. `siteContent.team.members` is intentionally empty until the team supplies verified details. Add a `TeamMember` with `name`, `role`, `bio`, and optional `photo` (a path under `frontend/public/`) and `links` to show a profile. Do not add unverified university endorsement, people, model results or accuracy claims.

Waste handling guidance and category names remain API-backed; edit the backend knowledge source rather than duplicating it in this static copy file.

## Run locally

From the repository root, start the API and Vite frontend with:

```powershell
./dev.ps1
```

`dev.ps1` opens `http://127.0.0.1:5175` and runs FastAPI on port 8001. For manual development, run FastAPI on port 8000 and Vite on port 5173; then open `http://127.0.0.1:5173`. The frontend-only Vite proxy forwards `/api` to port 8000.

## Behavior and QA notes

- Real uploads use `POST /api/v1/scans`; the user can draw a region for a second detection through `POST /api/v1/scans/region`. Per-detection corrections and recommendation sessions remain isolated. Chat calls the configured Groq model for every question, with KB context when available and KB fallback on provider failure.
- The sample action submits the repository's sample image to the same scan API. Its returned `mode=demo` is labeled as illustrative, with no fabricated confidence values. Real inference display depends on the backend response and available checkpoint.
- `npm ci` and `npm run build` pass in a clean temporary frontend copy. From the repository root, `.\.venv\Scripts\python.exe -m pytest -q` passes (53 tests; one Starlette deprecation warning). Browser smoke checks verified the mobile menu, no horizontal overflow at 390 px, the sample API response with three illustrative results, per-object label correction and synchronized box label, and a knowledge-base assistant response. The browser currently reports demo mode; real-checkpoint inference was not claimed.
- The guide's local `file://` reference could not be opened in the browser automation surface, so a reference-vs-React screenshot comparison was not recorded. The React app itself was opened and visually inspected in the browser.
