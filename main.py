"""
毎日 JST 21:00 にAI投稿をXに自動投稿し、LINE通知を送るスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date

from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    fetch_rss_headlines,
    select_best_post,
    NewsItem,
)
from twitter_client import post_tweet

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
    try:
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[LINE通知失敗] {e}")
        return False


def build_line_posted_message(tweet_text: str, tweet_url: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    return (
        f"\n✅ 今日({today})のX投稿完了 [{source}]\n"
        "─" * 20 + "\n"
        f"{tweet_text}\n"
        "─" * 20 + "\n"
        f"🔗 {tweet_url}"
    )


def build_line_draft_message(posts: list[str], source: str) -> str:
    """X投稿に失敗した場合の下書き通知"""
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n⚠️ 今日({today})のX投稿案（手動投稿お願いします）[{source}]",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    # X投稿APIが使えるかチェック
    x_enabled = all(
        os.environ.get(k)
        for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    )

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    selected_item: NewsItem | None = None
    source = "AIニュース"

    # Note記事から生成（未投稿のもの優先）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # NOTE_URL を抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.replace("NOTE_URL:", "").strip()
                break

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        source = f"Note: {note_file.stem}"

    # RSSニュースから生成（Note候補がない or Note生成に失敗した場合）
    if not posts:
        news_items = fetch_rss_headlines()
        posts, selected_item = generate_posts_from_rss(news_items)
        source = "AIニュース"

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    best_post = select_best_post(posts)
    image_url = selected_item.image_url if selected_item else None

    today_str = date.today().isoformat()

    # X に直接投稿
    if x_enabled:
        tweet_url = post_tweet(best_post, image_url=image_url)

        if tweet_url:
            print(f"[X投稿完了] {tweet_url}")
            append_to_log(f"x_posted\t{today_str}\t{tweet_url}")

            # LINE通知（何を投稿したか）
            if line_token and line_user_id:
                msg = build_line_posted_message(best_post, tweet_url, source)
                send_line_message(line_token, line_user_id, msg)
            return

        # X投稿失敗 → 下書きをLINEに送る
        print("[X投稿失敗] LINE下書き通知に切り替え")
        if line_token and line_user_id:
            msg = build_line_draft_message(posts, source)
            if send_line_message(line_token, line_user_id, msg):
                append_to_log(f"line_draft\t{today_str}\tfailed_x_post")
                print("[LINE下書き通知完了]")
        sys.exit(1)

    else:
        # X APIキー未設定 → LINEに下書き通知（既存動作）
        print("[X API未設定] LINE下書き通知モード")
        if line_token and line_user_id:
            msg = build_line_draft_message(posts, source)
            if send_line_message(line_token, line_user_id, msg):
                log_key = unposted[0].name if unposted else "rss"
                append_to_log(f"{log_key}\t{today_str}\tline_notified")
                print(f"[LINE通知完了] {source}")
        else:
            print("[スキップ] LINE認証情報未設定")
            for i, p in enumerate(posts[:3], 1):
                print(f"\n--- 案{i} ---\n{p}")


if __name__ == "__main__":
    main()
