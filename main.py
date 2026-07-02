"""
毎日 JST 21:00 に最新AIニュースからバイラル投稿を生成し、
X に自動投稿 ＋ LINE で通知するスクリプト。
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
    select_best_post,
)
from tweet_poster import post_tweet, build_tweet_url

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


# ─────────────────────────────────────────────
# ログ管理
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# LINE 通知
# ─────────────────────────────────────────────

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
    posts: list[str],
    source: str,
    posted_tweet_id: str | None = None,
    best_post: str = "",
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 20,
    ]

    if posted_tweet_id:
        tweet_url = build_tweet_url(posted_tweet_id)
        lines.append(f"\n✅ 自動投稿済み！\n🔗 {tweet_url}")
        lines.append(f"\n📝 投稿内容:\n{best_post}")
        lines.append("─" * 20)
        lines.append("\n📋 他の候補案:")

    for i, post in enumerate(posts[:3], 1):
        if post == best_post and posted_tweet_id:
            continue
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)

    if not posted_tweet_id:
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────

def _has_x_credentials() -> bool:
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    return all(os.environ.get(k) for k in required)


def run(posts: list[str], source: str) -> None:
    """投稿候補を受け取り、X投稿 ＋ LINE通知を実行"""
    if not posts:
        print(f"[{source}] 投稿候補が生成できませんでした。")
        return

    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    best = select_best_post(posts)
    posted_tweet_id: str | None = None

    # X 自動投稿
    if _has_x_credentials():
        posted_tweet_id = post_tweet(best)
        if posted_tweet_id:
            print(f"[X投稿完了] {build_tweet_url(posted_tweet_id)}")
        else:
            print("[X投稿失敗] LINE通知のみ送信します")
    else:
        print("[X認証情報なし] X_API_KEY 等が未設定のため、LINEのみ通知します")

    # LINE 通知
    if line_token and line_user_id:
        message = build_line_message(posts, source, posted_tweet_id, best)
        ok = send_line_message(line_token, line_user_id, message)
        print(f"[LINE通知{'完了' if ok else '失敗'}]")
    else:
        print("[LINE設定なし] 通知をスキップします")

    # ログ記録
    tweet_id_str = posted_tweet_id or "line_notified"
    append_to_log(f"{source}\t{date.today()}\t{tweet_id_str}")


def main() -> None:
    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            run(posts, f"Note:{note_file.stem}")
            return

    # RSSニュースから生成
    posts, _ = generate_posts_from_rss()
    if posts:
        run(posts, "AIニュース")
        return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
