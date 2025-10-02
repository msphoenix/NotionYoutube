"""Import a YouTube playlist into a Notion database."""

import os
import json
import subprocess
import logging
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client

# --- LOGGING CONFIG ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- CONFIG ---
load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
PLAYLIST_URL = f"https://www.youtube.com/playlist?list={PLAYLIST_ID}"
PRIORITY = os.getenv("PRIORITY")
TOPIC_LIST = os.getenv("TOPIC_LIST")
TOPIC = [t.strip() for t in TOPIC_LIST.split(",") if t.strip()] if TOPIC_LIST else []
LOCAL_UTC_OFFSET = 2  # Adjust if needed

if (
    not NOTION_TOKEN
    or not DATABASE_ID
    or not PLAYLIST_ID
    or not PRIORITY
    or TOPIC_LIST is None
):
    logging.error("One or more required environment variables are missing.")
    raise ValueError(
        "NOTION_TOKEN, DATABASE_ID, PLAYLIST_ID, PRIORITY, and TOPIC must be set in the .env file"
    )

# --- INIT ---
notion = Client(auth=NOTION_TOKEN)


def run_yt_dlp(args: list[str]) -> dict:
    """Run yt-dlp with given args and return parsed JSON output."""
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if not result.stdout.strip():
        logging.warning("yt-dlp returned no output.")
        return {}

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        logging.warning(
            "yt-dlp returned invalid JSON. First 200 chars:\n%s", result.stdout[:200]
        )
        return {}


def fetch_video_metadata(video_url: str) -> tuple[str | None, int | None]:
    """Fetch upload date and duration of a video."""
    data = run_yt_dlp(
        ["yt-dlp", "-J", "--skip-download", "--no-check-formats", video_url]
    )
    if not isinstance(data, dict):
        return None, None

    # Parse upload date
    upload_date_str = data.get("upload_date")
    og_added_iso = (
        datetime.strptime(upload_date_str, "%Y%m%d").date().isoformat()
        if upload_date_str
        else None
    )

    return og_added_iso, data.get("duration")


def fetch_playlist_videos(playlist_url: str) -> tuple[list[dict], str]:
    """Fetch all videos in a YouTube playlist."""
    flat_data = run_yt_dlp(["yt-dlp", "-J", "--flat-playlist", playlist_url])
    playlist_name = flat_data.get("title", "Unknown Playlist")
    flat_entries = flat_data.get("entries", [])

    videos = []

    for _, entry in enumerate(flat_entries, start=1):
        if not entry:  # private/unavailable video placeholder
            videos.append(
                {
                    "title": f"Private Video -> {playlist_name}",
                    "url": None,
                    "og_added_iso": None,
                    "length_sec": None,
                    "private": True,
                }
            )
            continue

        video_id = entry.get("id")
        video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
        raw_title = entry.get("title")
        is_private = not raw_title or raw_title.lower() == "[private video]"
        title = raw_title if not is_private else f"Private Video -> {playlist_name}"

        og_added_iso, length_sec = (None, None)
        if not is_private and video_url:
            og_added_iso, length_sec = fetch_video_metadata(video_url)

        videos.append(
            {
                "title": title,
                "url": video_url,
                "og_added_iso": og_added_iso,
                "length_sec": length_sec,
                "private": is_private,
            }
        )

    logging.info("📋 Found %d videos in playlist '%s'.", len(videos), playlist_name)
    return videos, playlist_name


def fetch_existing_urls(database_id: str) -> set[str]:
    """Fetch existing video URLs from Notion database to avoid duplicates."""
    existing_urls = set()
    next_cursor = None

    while True:
        query = notion.databases.query(
            database_id=database_id, start_cursor=next_cursor
        )
        for page in query["results"]:
            url_property = page["properties"].get("URL", {})
            if url_property.get("url"):
                existing_urls.add(url_property["url"])

        if not query.get("has_more"):
            break
        next_cursor = query["next_cursor"]

    logging.info("🔎 Found %d existing entries in Notion.", len(existing_urls))
    return existing_urls


def add_videos_to_notion(
    videos: list[dict], playlist_name: str, existing_urls: set[str]
) -> None:
    """Add new videos to Notion database."""
    added_count = 0

    for v in videos:
        if v["url"] in existing_urls:
            logging.info("⏩ Skipped (already exists): %s", v["title"])
            continue

        properties = {
            "Name": {"title": [{"text": {"content": v["title"]}}]},
            "Priority": {"select": {"name": PRIORITY}},
            "Topic": {"multi_select": [{"name": t} for t in TOPIC]},
            "Playlist Name": {"rich_text": [{"text": {"content": playlist_name}}]},
        }

        if v["private"]:
            properties["Status"] = {"select": {"name": "On Hold"}}

        if v.get("url"):
            properties["URL"] = {"url": v["url"]}
        if v.get("og_added_iso"):
            properties["OG ADDED"] = {"date": {"start": v["og_added_iso"]}}
        if v.get("length_sec") is not None:
            properties["Length Sec"] = {"number": v["length_sec"]}

        icon = (
            {"emoji": "🔒"}
            if v["private"]
            else {
                "external": {
                    "url": "https://www.iconsdb.com/icons/preview/black/play-5-xl.png"
                }
            }
        )
        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            icon=icon,
            properties=properties,
        )
        logging.info("✅ Added %s", v["title"])
        added_count += 1

    logging.info("🎉 Done. Added %d new videos to Notion.", added_count)


if __name__ == "__main__":
    playlist_videos, playlist_title = fetch_playlist_videos(PLAYLIST_URL)
    notion_existing_urls = fetch_existing_urls(DATABASE_ID)
    add_videos_to_notion(playlist_videos, playlist_title, notion_existing_urls)
