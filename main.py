"""
毎日21:00 JST にAI投稿を自動生成・X投稿してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
import tweepy
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
X_USERNAME = "GAUCHE_cellist"


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
    """Xに投稿してツイートIDを返す。APIキー未設定または失敗時はNone"""
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    if not all(os.environ.get(k) for k in required):
        print("[X投稿スキップ] APIキーが未設定です（LINE通知のみ実行）")
        return None
    try:
        client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_SECRET"],
        )
        response = client.create_tweet(text=text)
        tweet_id = str(response.data["id"])
        print(f"[X投稿完了] https://x.com/{X_USERNAME}/status/{tweet_id}")
        return tweet_id
    except Exception as e:
        print(f"[X投稿エラー] {e}")
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


def build_line_message(posts: list[str], source: str, tweet_id: str | None = None) -> str:
    today = date.today().strftime("%Y/%m/%d")
    sep = "─" * 20

    if tweet_id:
        tweet_link = f"https://x.com/{X_USERNAME}/status/{tweet_id}"
        lines = [
            f"\n✅ {today} X自動投稿完了 [{source}]",
            sep,
            f"\n【投稿内容】\n{posts[0] if posts else ''}",
            f"\n🔗 {tweet_link}",
            sep,
        ]
        if len(posts) > 1:
            lines.append("\n📋 他の候補（追加で手動投稿できます）:")
            for i, post in enumerate(posts[1:3], 2):
                lines.append(f"\n【案{i}】\n{post}")
                lines.append(sep)
    else:
        lines = [
            f"\n🤖 {today} 投稿案 [{source}]",
            "⚠️ X自動投稿未実施（APIキー確認 or 手動で投稿してください）",
            sep,
        ]
        for i, post in enumerate(posts[:3], 1):
            lines.append(f"\n【案{i}】\n{post}")
            lines.append(sep)
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")

    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # Note記事から生成・投稿
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            tweet_id = post_to_x(posts[0])
            message = build_line_message(posts, f"Note: {note_file.stem}", tweet_id)
            if send_line_message(line_token, line_user_id, message):
                log_id = tweet_id or "line_notified"
                append_to_log(f"{note_file.name}\t{date.today()}\t{log_id}")
                print(f"[完了] Note: {note_file.name}")
                return

    # RSSニュースから生成・投稿
    posts = generate_posts_from_rss()
    if posts:
        tweet_id = post_to_x(posts[0])
        message = build_line_message(posts, "AIニュース", tweet_id)
        if send_line_message(line_token, line_user_id, message):
            log_id = tweet_id or "line_notified"
            append_to_log(f"rss\t{date.today()}\t{log_id}")
            print("[完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
