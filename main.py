"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import PostCandidate, generate_posts_from_notes, generate_posts_from_rss

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_MAX_CHARS = 4900


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


def build_line_message(candidates: list[PostCandidate], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🤖 今日({today})のX投稿案 [{source}]",
        "━" * 22,
    ]

    for i, c in enumerate(candidates[:3], 1):
        lines.append(f"\n【案{i}】")
        lines.append(c.tweet)

        if c.buzz_reason:
            lines.append(f"\n💡 {c.buzz_reason}")
        if c.image_hint:
            lines.append(f"🖼 {c.image_hint}")
        if c.thread_hook:
            lines.append(f"🧵 {c.thread_hook}")
        if c.source_url:
            lines.append(f"🔗 {c.source_url}")

        lines.append("\n" + "─" * 22)

    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    message = "\n".join(lines)

    # LINEは5000文字制限のため、超過する場合は末尾を切り詰める
    if len(message) > LINE_MAX_CHARS:
        message = message[:LINE_MAX_CHARS] + "\n…（省略）"
    return message


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = (
            FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        )

        # NOTE_URL があれば抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split("NOTE_URL:", 1)[1].strip()
                break

        candidates = generate_posts_from_notes(note_text, feedback_text, note_url)
        if candidates:
            message = build_line_message(candidates, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成（メイン経路）
    candidates = generate_posts_from_rss()
    if candidates:
        message = build_line_message(candidates, "AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
