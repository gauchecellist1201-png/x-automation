"""
毎日 JST 21:00 にAI投稿案を生成→Xに自動投稿→LINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss, select_best_tweet

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


def try_post_to_x(best_tweet: str) -> str | None:
    """X API キーが設定されていれば投稿してURLを返す。なければNone。"""
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    if not all(os.environ.get(k) for k in required):
        return None

    from x_poster import post_tweet, tweet_url
    tweet_id = post_tweet(best_tweet)
    if tweet_id:
        return tweet_url(tweet_id)
    return None


def build_line_message(
    posts: list[str],
    source: str,
    best_tweet: str = "",
    select_reason: str = "",
    x_url: str = "",
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🤖 今日({today})のX投稿案 [{source}]", "─" * 20]

    if best_tweet:
        status = f"✅ X投稿済み\n{x_url}" if x_url else "📋 最優秀案（手動投稿推奨）"
        lines += [
            f"\n🏆 自動選定ベスト案 [{select_reason}]",
            f"{status}",
            "",
            best_tweet,
            "─" * 20,
            "\n📝 全候補：",
        ]

    for i, post in enumerate(posts, 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)

    if not x_url:
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")

    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = ""

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_url = ""
        # naoki_profile.md の NOTE_URL を取得
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split(":", 1)[1].strip()
        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            source = f"Note: {note_file.stem}"
            log_key = note_file.name

    # RSSニュースから生成（Noteが空か候補なしの場合）
    if not posts:
        posts = generate_posts_from_rss()
        source = "AIニュース"
        log_key = "rss"

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # ベスト案を自動選定
    best_tweet, select_reason = select_best_tweet(posts)

    # X に自動投稿（APIキーがあれば）
    x_url = try_post_to_x(best_tweet) if best_tweet else None
    if x_url:
        print(f"[X投稿完了] {x_url}")
        log_status = f"x_posted:{x_url}"
    else:
        log_status = "line_notified"

    # LINE通知
    message = build_line_message(posts, source, best_tweet, select_reason, x_url or "")
    if send_line_message(line_token, line_user_id, message):
        append_to_log(f"{log_key}\t{date.today()}\t{log_status}")
        print(f"[LINE通知完了] {source}")
    else:
        print("[LINE通知失敗]")
        sys.exit(1)


if __name__ == "__main__":
    main()
