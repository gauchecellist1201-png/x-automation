"""
毎日 JST 21:00 にAI投稿を生成・Xへ自動投稿し・LINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date

from content_gen import TweetCandidate, generate_posts_from_notes, generate_posts_from_rss
from tweet_poster import post_tweet

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
    candidates: list[TweetCandidate],
    source: str,
    posted_tweet_id: str | None,
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    status = (
        f"✅ 自動投稿済み: https://x.com/i/status/{posted_tweet_id}"
        if posted_tweet_id
        else "⚠️ 自動投稿失敗 → 手動でコピーしてXに投稿してください"
    )

    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        status,
        "─" * 20,
    ]
    for i, c in enumerate(candidates[:3], 1):
        marker = "👉 【投稿済み】" if (i == 1 and posted_tweet_id) else f"【案{i}】"
        lines.append(f"\n{marker}\n{c['text']}")
        if c.get("source_url"):
            lines.append(f"🔗 元記事: {c['source_url']}")
        lines.append("─" * 20)

    return "\n".join(lines)


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    candidates: list[TweetCandidate] = []
    source_label = ""

    # Note記事から生成（未投稿のものがあれば優先）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # NOTE_URL を記事本文から抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split("NOTE_URL:", 1)[1].strip()
                break

        candidates = generate_posts_from_notes(note_text, feedback_text, note_url)
        source_label = f"Note: {note_file.stem}"
        if candidates:
            append_to_log(f"{note_file.name}")  # 使用済みとしてマーク

    # RSSニュースから生成（Noteが尽きた場合 or 生成失敗）
    if not candidates:
        candidates = generate_posts_from_rss()
        source_label = "AIニュース"

    if not candidates:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # 最も良い案（先頭）をXに自動投稿
    best = candidates[0]
    tweet_id = post_tweet(best["text"], best.get("image_url"))

    log_entry = f"rss\t{date.today()}\t{tweet_id or 'post_failed'}"
    if source_label.startswith("Note:"):
        note_name = source_label.replace("Note: ", "") + ".md"
        log_entry = f"{note_name}\t{date.today()}\t{tweet_id or 'post_failed'}"
    append_to_log(log_entry)

    # LINEに通知（任意：認証情報がなければスキップ）
    if line_token and line_user_id:
        message = build_line_message(candidates, source_label, tweet_id)
        if send_line_message(line_token, line_user_id, message):
            print(f"[LINE通知完了] {source_label}")
        else:
            print("[LINE通知失敗]")

    if tweet_id:
        print(f"[完了] {source_label} → https://x.com/i/status/{tweet_id}")
    else:
        print(f"[X投稿失敗] {source_label} → 手動投稿が必要です")
        sys.exit(1)


if __name__ == "__main__":
    main()
