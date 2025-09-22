"""Importing youtube video details to notion database"""

import subprocess
import json
from datetime import datetime
import os
from dotenv import load_dotenv
from notion_client import Client

# Load environment variables from .env
load_dotenv()

# --- CONFIG ---
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")
PLAYLIST_URL = "https://www.youtube.com/playlist?list="
PRIORITY = "High"
TOPIC = ["Git"]
LOCAL_UTC_OFFSET = 2  # Adjust to your local timezone
TEST = 2

# --- INIT ---
notion = Client(auth=NOTION_TOKEN)

# --- STEP 1: Get flat playlist to include private videos ---
flat_result = subprocess.run(
    ["yt-dlp", "-J", "--flat-playlist", PLAYLIST_URL],
    capture_output=True,
    text=True,
    check=False,
)
flat_data = json.loads(flat_result.stdout)
playlist_name = flat_data.get("title", "Unknown Playlist")
flat_entries = flat_data.get("entries", [])

videos = []

for index, e in enumerate(flat_entries, start=1):
    if e is None:
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

    video_id = e.get("id")
    video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
    raw_title = e.get("title")
    is_private = raw_title is None or raw_title.lower() == "[private video]"
    title = (
        raw_title if not is_private else f"Private Video #{index} -> {playlist_name}"
    )

    # OG ADDED only for public videos
    OG_ADDED_ISO = None
    LENGTH_SEC = None
    if not is_private and video_url:
        full_result = subprocess.run(
            ["yt-dlp", "-J", video_url], capture_output=True, text=True, check=False
        )
        full_data = json.loads(full_result.stdout)
        upload_date_str = full_data.get("upload_date")
        if upload_date_str:
            OG_ADDED_ISO = (
                datetime.strptime(upload_date_str, "%Y%m%d").date().isoformat()
            )
        LENGTH_SEC = full_data.get("duration")

    videos.append(
        {
            "title": title,
            "url": video_url,
            "og_added_iso": OG_ADDED_ISO,
            "length_sec": LENGTH_SEC,
            "private": is_private,
        }
    )


print(f"Found {len(videos)} videos in playlist (including private/unavailable).")

# --- STEP 3: Get existing URLs in Notion ---
existing_urls = set()
query = notion.databases.query(database_id=DATABASE_ID)
for page in query["results"]:
    url_property = page["properties"].get("URL", {})
    if url_property.get("url"):
        existing_urls.add(url_property["url"])

print(f"Found {len(existing_urls)} existing entries in Notion.")

# --- STEP 4: Add videos to Notion ---
ADDED_COUNT = 0
for v in videos:
    if v["url"] in existing_urls:
        print(f"Skipped (already exists): {v['title']}")
        continue

    # Build properties
    properties = {
        "Name": {"title": [{"text": {"content": v["title"]}}]},
        "Priority": {"select": {"name": PRIORITY}},
        "Topic": {"multi_select": [{"name": t} for t in TOPIC]},
        "Status": {"select": {"name": "On Hold"}} if v["private"] else None,
        "Playlist Name": {"rich_text": [{"text": {"content": playlist_name}}]},
    }

    # URL and OG ADDED
    if v["url"]:
        properties["URL"] = {"url": v["url"]}
    if v.get("og_added_iso"):
        properties["OG ADDED"] = {"date": {"start": v["og_added_iso"]}}
    if v.get("length_sec") is not None:  # --- ADDED ---
        properties["Length Sec"] = {"number": v["length_sec"]}

    # Determine icon
    icon = (
        {"emoji": "🔒"}
        if v["private"]
        else {
            "external": {
                "url": "https://www.iconsdb.com/icons/preview/black/play-5-xl.png"
            }
        }
    )

    # Remove None values (Notion API does not accept null)
    properties = {k: v for k, v in properties.items() if v is not None}

    # Create the page in Notion
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        icon=icon,
        properties=properties,
    )

    print(f"Added {'private video' if v['private'] else ''}: {v['title']}")
    ADDED_COUNT += 1

print(f"\n✅ Done. Added {ADDED_COUNT} new videos to Notion.")
