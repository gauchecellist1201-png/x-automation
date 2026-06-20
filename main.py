"""
毎日21:00 JST にAI投稿をXへ自動投稿し、LINEに通知するスクリプト
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
    select_best_tweet,
)
from x_poster import post_tweet

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


def build_line_message(
    posted_tweet: str,
    tweet_id: str | None,
    other_candidates: list[str],
    source: str,
    news_link: str = "",
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🤖 {today}のAI投稿 [{source}]"]

    if tweet_id:
        tweet_url = f"https://x.com/i/web/status/{tweet_id}"
        lines += [
            "─" * 20,
            f"\n✅ Xに自動投稿済み",
            f"🔗 {tweet_url}",
            f"\n【投稿内容】\n{posted_tweet}",
        ]
    else:
        lines += [
            "─" * 20,
            "\n⚠️ X投稿に失敗しました（手動で投稿してください）",
            f"\n【投稿候補】\n{posted_tweet}",
        ]

    if news_link:
        lines.append(f"\n📰 参照記事: {news_link}")

    if other_candidates:
        lines.append("\n─" * 10)
        lines.append("【他の投稿案】")
        for i, c in enumerate(other_candidates[:2], 2):
            lines.append(f"\n案{i}: {c}")

    lines.append("\n─" * 20)
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted_log = load_posted_log()

    # ログに記録されていないNoteファイルを取得
    # ただし「ファイル名のみ」でなく「ファイル名\t*」でマッチ
    logged_filenames = {entry.split("\t")[0] for entry in posted_log}
    unposted = [
        p for p in (NOTES_DIR.glob("*.md") if NOTES_DIR.exists() else [])
        if p.name not in logged_filenames
    ]

    posts: list[str] = []
    news_link = ""
    source = ""

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # NoteのURLをプロフィールから抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.replace("NOTE_URL:", "").strip()
                break

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        source = f"Note: {note_file.stem}"
        log_key = note_file.name

    # RSSニュースから生成
    if not posts:
        posts, news_link = generate_posts_from_rss()
        source = "AIニュース"
        log_key = "rss"

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # バズりやすい投稿を選択して投稿
    best_tweet = select_best_tweet(posts)
    others = [p for p in posts if p != best_tweet]

    tweet_id = post_tweet(best_tweet)

    # LINE通知
    message = build_line_message(best_tweet, tweet_id, others, source, news_link)
    line_ok = send_line_message(line_token, line_user_id, message)

    if line_ok:
        print(f"[LINE通知完了] {source}")
    else:
        print(f"[LINE通知失敗] {source}")

    # ログ記録
    status = tweet_id if tweet_id else "x_failed"
    append_to_log(f"{log_key}\t{date.today()}\t{status}")
    print(f"[完了] source={source}, tweet_id={tweet_id}")


if __name__ == "__main__":
    main()
