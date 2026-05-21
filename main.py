"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date, timedelta
from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    PostCandidate,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")
NOTE_REUSE_DAYS = 14  # 同じノートを再利用するまでの最短日数

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> dict[str, date]:
    """ファイル名 -> 最終投稿日 のマップを返す"""
    result: dict[str, date] = {}
    if not LOG_FILE.exists():
        return result
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            filename = parts[0]
            try:
                posted_date = date.fromisoformat(parts[1])
                # 同じファイルが複数回ある場合は最新を保持
                if filename not in result or posted_date > result[filename]:
                    result[filename] = posted_date
            except ValueError:
                continue
    return result


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_available_notes(posted_log: dict[str, date]) -> list[Path]:
    """NOTE_REUSE_DAYS 以内に投稿済みのノートを除外して返す"""
    if not NOTES_DIR.exists():
        return []
    today = date.today()
    available = []
    for p in NOTES_DIR.glob("*.md"):
        last_posted = posted_log.get(p.name)
        if last_posted is None or (today - last_posted).days >= NOTE_REUSE_DAYS:
            available.append(p)
    return available


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
        if c.source_url:
            lines.append(f"\n📎 記事URL: {c.source_url}")
        lines.append("─" * 22)

    lines.append(
        "\n✅ 気に入った案をコピーしてXに投稿してください！\n"
        "💡 記事URLをツイートに含めるとカードが展開されます"
    )
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted_log = load_posted_log()
    available_notes = get_available_notes(posted_log)

    # Note記事から生成
    if available_notes:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # ノート内の NOTE_URL を抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split(":", 1)[1].strip()
                break

        candidates = generate_posts_from_notes(note_text, feedback_text, note_url)
        if candidates:
            message = build_line_message(candidates, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    candidates = generate_posts_from_rss()
    if candidates:
        source_title = candidates[0].source_title or "AIニュース"
        message = build_line_message(candidates, source_title[:30])
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
