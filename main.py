"""
X (Twitter) 自動投稿スクリプト
X API v2 Free プラン（書き込み専用）対応
"""

import os
import sys
import random
import tweepy
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")


def load_posted_log() -> set[str]:
    if not LOG_FILE.exists():
        return set()
    return set(LOG_FILE.read_text(encoding="utf-8").splitlines())


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_unposted_notes(posted: set[str]) -> list[Path]:
    if not NOTES_DIR.exists():
        return []
    return [p for p in NOTES_DIR.glob("*.md") if p.name not in posted]


def post_tweet(client: tweepy.Client, text: str) -> str | None:
    response = client.create_tweet(text=text)
    return str(response.data["id"])


def main() -> None:
    api_key = os.environ["X_API_KEY"]
    api_secret = os.environ["X_API_SECRET"]
    access_token = os.environ["X_ACCESS_TOKEN"]
    access_secret = os.environ["X_ACCESS_SECRET"]

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    candidates: list[str] = []

    # Note記事からの投稿案（未投稿ファイルが存在する場合）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_posts = generate_posts_from_notes(note_text, feedback_text)
        candidates.extend(note_posts)

        if note_posts:
            # 投稿済みとしてログに記録（ファイル名のみ）
            posted_key = f"{note_file.name}"
            chosen = note_posts[0]
            tweet_id = post_tweet(client, chosen)
            if tweet_id:
                append_to_log(f"{posted_key}\t{date.today()}\t{tweet_id}")
                print(f"[Note投稿] {chosen}")
                return

    # RSSフィードからのAIニュース投稿
    rss_posts = generate_posts_from_rss()
    if rss_posts:
        chosen = rss_posts[0]
        tweet_id = post_tweet(client, chosen)
        if tweet_id:
            append_to_log(f"rss\t{date.today()}\t{tweet_id}")
            print(f"[RSS投稿] {chosen}")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
