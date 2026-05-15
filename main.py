"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
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
    generate_thread_opener,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

# 同一ノートを再利用するまでの最小間隔（日数）
NOTE_REUSE_INTERVAL_DAYS = 7


def load_posted_log() -> list[dict]:
    """ログをパース。各行: filename\tdate\tstatus"""
    if not LOG_FILE.exists():
        return []
    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            entries.append({"name": parts[0], "date": parts[1], "status": parts[2] if len(parts) > 2 else ""})
    return entries


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_available_notes(log_entries: list[dict]) -> list[Path]:
    """NOTE_REUSE_INTERVAL_DAYS 以上前に使ったノートを再利用可能として返す"""
    if not NOTES_DIR.exists():
        return []

    today = date.today()
    recent_notes: set[str] = set()
    for entry in log_entries:
        try:
            used_date = date.fromisoformat(entry["date"])
            delta = (today - used_date).days
            if delta < NOTE_REUSE_INTERVAL_DAYS:
                recent_notes.add(entry["name"])
        except ValueError:
            continue

    all_notes = list(NOTES_DIR.glob("*.md"))
    available = [p for p in all_notes if p.name not in recent_notes]
    # 全件が最近使用済みの場合は全て返す（枯渇防止）
    return available if available else all_notes


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
    image_suggestion: str = "",
    thread_opener: list[str] | None = None,
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 22,
    ]

    for i, post in enumerate(posts[:5], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 22)

    if thread_opener:
        lines.append("\n🧵 スレッド冒頭案（リーチ拡大）")
        lines.append("─" * 22)
        for i, t in enumerate(thread_opener[:2], 1):
            lines.append(f"\n【スレッド案{i}】\n{t}")
        lines.append("─" * 22)

    if image_suggestion:
        lines.append(f"\n📸 画像提案（案1向け）\n{image_suggestion}")
        lines.append("─" * 22)

    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💬 良かった投稿は data/feedback.txt に追記すると精度が上がります")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    log_entries = load_posted_log()
    available_notes = get_available_notes(log_entries)

    # Note記事から生成（70%の確率で優先）
    if available_notes and random.random() < 0.7:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # Note内のURLを抽出
        note_url = ""
        for line in note_text.splitlines():
            if "NOTE_URL:" in line:
                note_url = line.split("NOTE_URL:")[-1].strip()
                break

        posts, image_suggestion = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            thread_openers = generate_thread_opener(note_file.stem.replace("_", "×"))
            message = build_line_message(
                posts,
                f"Note: {note_file.stem}",
                image_suggestion,
                thread_openers,
            )
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    posts, topic, image_suggestion = generate_posts_from_rss()
    if posts:
        thread_openers = generate_thread_opener(topic)
        message = build_line_message(posts, f"AIニュース: {topic}", image_suggestion, thread_openers)
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print(f"[LINE通知完了] RSSニュース: {topic}")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
