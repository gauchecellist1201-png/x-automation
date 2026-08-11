"""
毎日21:00 JST にAI関連投稿をXに自動投稿するスクリプト
"""

import os
import sys
import random
import requests
import tweepy
from pathlib import Path
from datetime import date
from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    pick_best_post,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


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


def post_to_x(text: str) -> str | None:
    """X API v2 でツイートを投稿し、投稿IDを返す"""
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )
    response = client.create_tweet(text=text)
    if response.data:
        return str(response.data["id"])
    return None


def send_line_message(token: str, user_id: str, message: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    return response.status_code == 200


def build_line_report(tweet: str, tweet_id: str | None, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    url = f"https://x.com/GAUCHE_cellist/status/{tweet_id}" if tweet_id else "投稿失敗"
    lines = [
        f"\n✅ 今日({today})のX投稿完了 [{source}]",
        "─" * 20,
        tweet,
        "─" * 20,
        f"🔗 {url}",
    ]
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = ""

    # Note記事から生成（優先）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_url_line = next(
            (l.split("NOTE_URL:")[-1].strip() for l in note_text.splitlines() if "NOTE_URL:" in l),
            "",
        )
        posts = generate_posts_from_notes(note_text, feedback_text, note_url_line)
        source = f"Note:{note_file.stem}"

    # RSSニュースから生成（フォールバック）
    if not posts:
        posts = generate_posts_from_rss()
        source = "RSS"

    if not posts:
        print("投稿候補の生成に失敗しました。")
        sys.exit(1)

    # 最もバズりそうな1本を選択
    best = pick_best_post(posts)
    if not best:
        print("有効な投稿候補がありませんでした。")
        sys.exit(1)

    print(f"[投稿選定] {best}")

    # X に投稿
    tweet_id = post_to_x(best)
    if tweet_id:
        append_to_log(f"{source}\t{date.today()}\t{tweet_id}")
        print(f"[X投稿完了] ID: {tweet_id}")
    else:
        append_to_log(f"{source}\t{date.today()}\tpost_failed")
        print("[X投稿失敗]")

    # LINE にも報告（設定されていれば）
    if line_token and line_user_id:
        report = build_line_report(best, tweet_id, source)
        send_line_message(line_token, line_user_id, report)


if __name__ == "__main__":
    main()
