import asyncio
import ipaddress
import json
import os
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AnyHttpUrl, BaseModel
import uvicorn


app = FastAPI(title="Vortex Wave API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_DOMAINS = ("youtube.com", "youtu.be", "soundcloud.com")


class ResolveRequest(BaseModel):
    url: AnyHttpUrl


def validate_media_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise HTTPException(status_code=400, detail="Only public HTTP(S) media URLs are supported.")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None

    if address and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved):
        raise HTTPException(status_code=400, detail="Private network addresses are not supported.")

    if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in ALLOWED_DOMAINS):
        raise HTTPException(
            status_code=400,
            detail="Supported sources are YouTube and SoundCloud.",
        )


async def run_ytdlp(*args: str, timeout: float = 45) -> str:
    try:
        process = await asyncio.create_subprocess_exec(
            "yt-dlp",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        if "process" in locals() and process.returncode is None:
            process.kill()
            await process.wait()
        raise HTTPException(status_code=504, detail="Media lookup timed out.") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="yt-dlp is not installed.") from exc

    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip().splitlines()
        detail = message[-1][:300] if message else "yt-dlp could not process this request."
        raise HTTPException(status_code=500, detail=detail)

    return stdout.decode("utf-8", errors="replace").strip()


@app.get("/api/healthz")
async def health_check():
    return {"status": "ok"}


@app.get("/api/search")
async def search_tracks(q: str = Query(min_length=1, max_length=160)):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query cannot be empty.")

    output = await run_ytdlp(
        f"ytsearch5:{query}",
        "--dump-json",
        "--flat-playlist",
        "--no-warnings",
        "--skip-download",
    )
    tracks = []
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail="Search provider returned invalid data.") from exc
        if not isinstance(entry, dict):
            continue

        track_id = str(entry.get("id") or "")
        extractor = str(entry.get("ie_key") or entry.get("extractor_key") or "").lower()
        source_url = entry.get("webpage_url") or entry.get("original_url")
        if not source_url and track_id and "youtube" in extractor:
            source_url = f"https://www.youtube.com/watch?v={track_id}"
        if not source_url and isinstance(entry.get("url"), str) and entry["url"].startswith(("http://", "https://")):
            source_url = entry["url"]
        thumbnails = entry.get("thumbnails") or []
        thumbnail = entry.get("thumbnail")
        if not thumbnail and thumbnails:
            thumbnail = thumbnails[-1].get("url") if isinstance(thumbnails[-1], dict) else None
        duration = entry.get("duration")
        tracks.append(
            {
                "id": track_id or str(source_url or entry.get("title") or len(tracks)),
                "title": entry.get("title") or "Untitled",
                "uploader": entry.get("uploader") or entry.get("channel") or entry.get("creator") or "Unknown artist",
                "thumbnail": thumbnail,
                "duration": int(duration) if isinstance(duration, (int, float)) else None,
                "webpage_url": source_url,
            }
        )

    return tracks


@app.post("/api/resolve")
async def resolve_stream(request: ResolveRequest):
    media_url = str(request.url)
    validate_media_url(media_url)
    output = await run_ytdlp("-g", "-f", "bestaudio", media_url, timeout=60)
    stream_url = next((line.strip() for line in output.splitlines() if line.strip()), None)
    if not stream_url:
        raise HTTPException(status_code=500, detail="No audio stream was returned.")
    return {"stream_url": stream_url, "status": "success"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
