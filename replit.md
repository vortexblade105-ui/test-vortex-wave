# Vortex Wave

An iOS music discovery and streaming app with an Expo client and a FastAPI audio-search and stream-resolution service.

## Run & Operate

- `python -m pip install -r requirements.txt && python server.py` — run the FastAPI backend
- `pnpm --filter @workspace/vortex-wave run dev` — run the iOS Expo client
- `pnpm run typecheck` — full typecheck across all packages
- Backend routes: `/api/search`, `/api/resolve`, and `/api/healthz`
- The API workflow supplies `PORT`; running the server manually defaults to port `8000`.

## Stack

- iOS client: React Native with Expo, JavaScript, and `expo-audio`
- Backend: Python, FastAPI, Uvicorn, and `yt-dlp`
- API: JSON over HTTP with permissive CORS for the mobile client

## Where things live

- `artifacts/vortex-wave/App.js` — search, player, playback queue, and navigation UI
- `artifacts/vortex-wave/src/services/api.js` — mobile requests for search and stream resolution
- `artifacts/vortex-wave/app.json` — iOS-only app configuration and background audio mode
- `server.py` — FastAPI endpoints and `yt-dlp` subprocess handling
- `requirements.txt` — backend Python dependencies

## Architecture decisions

- The mobile app reaches FastAPI through the shared `/api` service path; the Expo development domain is injected at runtime.
- Search results are resolved to direct audio URLs only when the listener starts a track.

## Product

- Search tracks, play and pause audio, seek within a track, skip through the queue, and continue background audio on iOS.

## User preferences

- Keep the app iOS-only; do not add Android-specific screens or behavior.
- Do not use `npx create-expo-app` or app-generation templates for future implementation work.

## Gotchas

- `server.py` reads the service-provided `PORT` and defaults to port `8000` when run manually.

## Pointers

- See the Expo skill for mobile workflow and preview details.
