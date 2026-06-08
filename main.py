"""
毎日21:00 JST にバズるAI投稿をXへ自動投稿し、LINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date

from content_gen import generate_posts_from_notes, generate_posts_from_rss
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
    posts: list[dict],
    source: str,
    tweet_id: str | None = None,
    posted_text: str = "",
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🤖 今日({today})のX投稿 [{source}]"]

    if tweet_id:
        lines.append(f"\n✅ X自動投稿済み！")
        lines.append(f"https://x.com/i/web/status/{tweet_id}")
        lines.append(f"\n投稿内容:\n{posted_text}")
        lines.append("─" * 20)
        if len(posts) > 1:
            lines.append("\n📋 ボツになった案（手動投稿可）:")
            for i, post in enumerate(posts[1:3], 2):
                lines.append(f"\n【案{i}】\n{post['text']}")
                if post.get("url"):
                    lines.append(post["url"])
                lines.append("─" * 20)
    else:
        lines.append("─" * 20)
        for i, post in enumerate(posts[:3], 1):
            lines.append(f"\n【案{i}】\n{post['text']}")
            if post.get("url"):
                lines.append(post["url"])
            lines.append("─" * 20)
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")

    return "\n".join(lines)


def has_x_credentials() -> bool:
    return all(
        os.environ.get(k)
        for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    )


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[dict] = []
    source = "AIニュース"

    # Note記事から生成（未投稿があれば優先）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            source = f"Note: {note_file.stem}"

    # Note生成なしor失敗 → RSSニュースから生成
    if not posts:
        posts = generate_posts_from_rss()

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # 最初の候補をXへ自動投稿
    tweet_id: str | None = None
    best = posts[0]
    tweet_body = best["text"]
    if best.get("url"):
        tweet_body = tweet_body + "\n" + best["url"]

    if has_x_credentials():
        tweet_id = post_tweet(tweet_body)
        status = tweet_id if tweet_id else "x_post_failed"
    else:
        print("[X投稿スキップ] X API認証情報が未設定")
        status = "line_notified"

    # LINE通知（X投稿結果 + 残り候補）
    if line_token and line_user_id:
        message = build_line_message(posts, source, tweet_id, tweet_body)
        if send_line_message(line_token, line_user_id, message):
            print(f"[LINE通知完了] source={source}")
        else:
            print("[LINE通知失敗]")

    # ログ記録
    log_key = best.get("url", "rss") or source
    append_to_log(f"{log_key}\t{date.today()}\t{status}")
    print(f"[完了] source={source}, status={status}")


if __name__ == "__main__":
    main()
