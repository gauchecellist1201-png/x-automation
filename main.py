"""
毎日21:00 JST にAI投稿案を生成し、X自動投稿 + LINE通知を行うスクリプト
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
    TweetCandidate,
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
    try:
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[LINE通知エラー] {e}")
        return False


def build_line_message(
    candidates: list[TweetCandidate], source: str, tweet_id: str = ""
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    posted_note = (
        f"\n✅ 案1をXに自動投稿済み\nhttps://x.com/i/web/status/{tweet_id}"
        if tweet_id
        else "\n⚠️ X自動投稿はスキップされました"
    )

    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]{posted_note}",
        "─" * 20,
    ]
    for i, c in enumerate(candidates[:3], 1):
        lines.append(f"\n【案{i}】\n{c.full_text}")
        lines.append("─" * 20)
    lines.append("\n💡 他の案もXに投稿したい場合はコピーしてどうぞ！")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    candidates: list[TweetCandidate] = []
    source = ""

    # Note記事から生成（未投稿のものがあれば優先）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = (
            FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        )
        candidates = generate_posts_from_notes(note_text, feedback_text)
        source = f"Note: {note_file.stem}"
        if candidates:
            append_to_log(f"{note_file.name}\t{date.today()}\tgenerated")

    # RSSニュースから生成（Noteがない or 生成失敗時）
    if not candidates:
        candidates = generate_posts_from_rss()
        source = "AIニュース"
        if candidates:
            append_to_log(f"rss\t{date.today()}\tgenerated")

    if not candidates:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # X自動投稿（最初の案＝最もバズりやすいと判断されたもの）
    tweet_id = post_tweet(candidates[0].full_text)
    if tweet_id:
        append_to_log(f"x_posted\t{date.today()}\t{tweet_id}")

    # LINE通知（全候補 + 投稿結果を通知）
    if line_token and line_user_id:
        message = build_line_message(candidates, source, tweet_id or "")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"line_notified\t{date.today()}\t{source}")
            print(f"[LINE通知完了] {source}")

    print(
        f"[完了] 投稿案{len(candidates)}件 / X投稿: {'成功 tweet_id=' + tweet_id if tweet_id else 'スキップ'}"
    )


if __name__ == "__main__":
    main()
