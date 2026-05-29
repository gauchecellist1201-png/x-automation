"""
毎日21:00 JST にAI投稿を生成・X投稿・LINE通知するスクリプト

環境変数:
  AUTO_POST=true          X への自動投稿を有効化（default: false）
  GENERATE_IMAGE=true     ビジュアルカードを生成して添付（default: false）
  LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID  LINE通知（省略可）
  X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET  X投稿用
  ANTHROPIC_API_KEY       Claude API
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


def build_line_message(posts: list[str], source: str, best: str, status: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:3], 1):
        marker = "★ 選択" if post == best else f"案{i}"
        lines.append(f"\n【{marker}】\n{post}")
        lines.append("─" * 20)
    lines.append(f"\n{status}")
    return "\n".join(lines)


def main() -> None:
    auto_post = os.environ.get("AUTO_POST", "false").lower() == "true"
    generate_image = os.environ.get("GENERATE_IMAGE", "false").lower() == "true"
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    # ── 1. 投稿候補を生成 ──────────────────────────────────────
    posted = load_posted_log()
    # Note記事は一度ログされても再利用可 (同じ記事から毎回異なる投稿を生成)
    unposted = get_unposted_notes(posted)
    all_notes = list(NOTES_DIR.glob("*.md")) if NOTES_DIR.exists() else []

    posts: list[str] = []
    source = "AIニュース"
    source_key = "rss"

    # Note記事優先 (未投稿 → 全体からランダム)
    note_pool = unposted if unposted else all_notes
    if note_pool:
        note_file = random.choice(note_pool)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        source = f"Note: {note_file.stem}"
        source_key = note_file.name

    if not posts:
        posts = generate_posts_from_rss()

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # ── 2. 最良ツイートを選択 ──────────────────────────────────
    best_post = select_best_post(posts)
    print(f"[選択済み] {best_post}")

    # ── 3. 画像カード生成 ──────────────────────────────────────
    image_path: Path | None = None
    if generate_image:
        from image_gen import create_ai_card
        image_path = create_ai_card(best_post, date_str=date.today().strftime("%Y.%m.%d"))

    # ── 4. X に投稿 ────────────────────────────────────────────
    tweet_id: str | None = None
    if auto_post:
        from tweet_poster import post_tweet
        tweet_id = post_tweet(best_post, str(image_path) if image_path else None)

    # ── 5. LINE 通知 ───────────────────────────────────────────
    if line_token and line_user_id:
        if tweet_id:
            status = f"✅ X投稿完了\nhttps://x.com/i/web/status/{tweet_id}"
        else:
            status = "📋 投稿案を生成しました（自動投稿OFF）\n気に入った案をコピーしてXに投稿してください！"
        message = build_line_message(posts, source, best_post, status)
        ok = send_line_message(line_token, line_user_id, message)
        print(f"[LINE通知] {'成功' if ok else '失敗'}")

    # ── 6. ログ更新 ────────────────────────────────────────────
    log_value = tweet_id if tweet_id else "line_notified"
    append_to_log(f"{source_key}\t{date.today()}\t{log_value}")
    print(f"[完了] {source} → {log_value}")


if __name__ == "__main__":
    main()
