# NotionYoutube Playlist Importer

This Python script imports videos from a YouTube playlist into a Notion database, including metadata such as title, duration, and upload date. It avoids duplicates and supports custom priority and topic tagging.

## Features

-   Fetches all videos from a YouTube playlist using `yt-dlp`
-   Adds each video as a page in your Notion database
-   Skips videos already present in Notion (by URL)
-   Supports custom priority and topic tags via `.env`
-   Logs progress and errors to the terminal

## Requirements

-   Python 3.9+
-   [yt-dlp](https://github.com/yt-dlp/yt-dlp) (must be installed and available in your PATH; you can also install it with pip: `pip install yt-dlp`)
-   [notion-client](https://github.com/ramnes/notion-sdk-py)
-   [python-dotenv](https://pypi.org/project/python-dotenv/)

Install dependencies:

```sh
pip install notion-client python-dotenv yt-dlp
```

## Setup

1. **Clone this repository.**

2. **Create a `.env` file in the project root:**

    ```
    NOTION_TOKEN=your_notion_integration_token
    DATABASE_ID=your_notion_database_id
    PLAYLIST_ID=your_youtube_playlist_id
    PRIORITY=your_priority_value
    TOPIC_LIST=comma,separated,topics
    ```

    Example:

    ```
    NOTION_TOKEN=ntn_fake_token_1234567890abcdef
    DATABASE_ID=1234567890abcdef1234567890abcdef
    PLAYLIST_ID=PL1234567890abcdef1234567890abcdef
    PRIORITY=m
    TOPIC_LIST=Python,AI
    ```

3. **Ensure your Notion database has the required properties (or edit this to create your own):**

    - Name (title)
    - Priority (select)
    - Topic (multi-select)
    - Playlist Name (rich text)
    - Status (select)
    - URL (url)
    - OG ADDED (date)
    - Length Sec (number)

4. **Run the script:**
    ```sh
    python import_playlist_to_notion.py
    ```

## Notes

-   The script will log progress and any issues to the terminal.
-   Make sure your Notion integration has access to the target database.
-   The script respects Notion API rate limits.

## License

MIT
