"""
毎日21:00 JST にAI投稿を自動生成してXに投稿し、LINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss
from x_post import post_tweet

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


def build_line_message(posted_text: str, tweet_id: str | None, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    status = f"✅ Xに投稿済み\nhttps://x.com/GAUCHE_cellist/status/{tweet_id}" if tweet_id else "⚠️ X投稿に失敗しました（手動投稿をご確認ください）"
    lines = [
        f"\n🤖 今日({today})のX投稿 [{source}]",
        "─" * 20,
        posted_text,
        "─" * 20,
        status,
    ]
    return "\n".join(lines)


def x_api_configured() -> bool:
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    return all(os.environ.get(k) for k in required)


def line_configured() -> bool:
    return bool(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN") and os.environ.get("LINE_USER_ID"))


def run(posts: list[str], source: str) -> bool:
    if not posts:
        return False

    # 最も良い案（1番目）を採用
    best_post = posts[0]

    tweet_id = None
    if x_api_configured():
        tweet_id = post_tweet(best_post)
        if tweet_id:
            print(f"[X投稿完了] {tweet_id}")
        else:
            print("[X投稿失敗]")
    else:
        print("[X API未設定] スキップします")

    if line_configured():
        token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
        user_id = os.environ["LINE_USER_ID"]
        message = build_line_message(best_post, tweet_id, source)
        if send_line_message(token, user_id, message):
            print("[LINE通知完了]")
    else:
        print("[LINE未設定] スキップします")
        print(f"投稿内容:\n{best_post}")

    return True


def main() -> None:
    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if run(posts, f"Note: {note_file.stem}"):
            append_to_log(f"{note_file.name}\t{date.today()}\tposted")
            return

    # RSSニュースから生成
    posts = generate_posts_from_rss()
    if run(posts, "AIニュース"):
        append_to_log(f"rss\t{date.today()}\tposted")
        return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
