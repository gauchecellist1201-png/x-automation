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
    generate_posts_from_rss_with_thread,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
MAX_LINE_CHARS = 4900  # LINE メッセージ上限の安全マージン


def load_posted_log() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            entries.append({"file": parts[0], "date": parts[1], "status": parts[2]})
    return entries


def get_recently_used_notes(log: list[dict], days: int = 7) -> set[str]:
    """直近N日以内に使ったNote名を返す"""
    today = date.today()
    recent = set()
    for entry in log:
        try:
            used_date = date.fromisoformat(entry["date"])
            delta = (today - used_date).days
            if delta < days and entry["file"].endswith(".md"):
                recent.add(entry["file"])
        except ValueError:
            continue
    return recent


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_fresh_notes(log: list[dict]) -> list[Path]:
    """直近7日に使っていないNoteファイルを返す"""
    if not NOTES_DIR.exists():
        return []
    recent = get_recently_used_notes(log, days=7)
    all_notes = list(NOTES_DIR.glob("*.md"))
    fresh = [p for p in all_notes if p.name not in recent]
    # 全て最近使用済みなら全ファイルを候補にする（フォールバック）
    return fresh if fresh else all_notes


def send_line_message(token: str, user_id: str, message: str) -> bool:
    # LINEの文字数上限に合わせてカット
    if len(message) > MAX_LINE_CHARS:
        message = message[:MAX_LINE_CHARS] + "\n…（省略）"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"[LINE送信失敗] status={response.status_code} body={response.text[:200]}")
    return response.status_code == 200


def build_line_message(posts: list[str], source: str, hook: str = "", thread_body: list[str] = None) -> str:
    today = date.today().strftime("%Y/%m/%d")
    sep = "─" * 22

    lines = [
        f"🤖 今日({today})のX投稿案",
        f"📌 ソース: {source}",
        sep,
    ]

    # スレッド形式があれば先頭に追加
    if hook:
        lines += [
            "\n🧵 【スレッド案】",
            f"1ツイート目（フック）:\n{hook}",
        ]
        if thread_body:
            for i, body in enumerate(thread_body, 2):
                lines.append(f"{i}ツイート目:\n{body}")
        lines.append(sep)

    # 単体ツイート案
    for i, post in enumerate(posts[:3], 1):
        char_count = len(post)
        lines.append(f"\n【案{i}】({char_count}文字)\n{post}")
        lines.append(sep)

    lines += [
        "",
        "✅ 気に入った案をXに投稿してください！",
        "💬 フィードバックは data/feedback.txt に追記してください",
    ]
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    log = load_posted_log()
    today_str = str(date.today())

    # --- 1. RSSから最新ニュースベースで生成（毎日必ず試みる）---
    posts = generate_posts_from_rss()
    thread_body, hook = [], ""

    # スレッド案も生成（RSSが成功した場合のみ）
    if posts:
        try:
            thread_body, hook = generate_posts_from_rss_with_thread()
        except Exception as e:
            print(f"[スレッド生成スキップ] {e}")

    source = "AIニュース（RSS）"

    # --- 2. RSSが空ならNoteから補完 ---
    if not posts:
        fresh_notes = get_fresh_notes(log)
        if fresh_notes:
            note_file = random.choice(fresh_notes)
            note_text = note_file.read_text(encoding="utf-8")
            feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
            posts = generate_posts_from_notes(note_text, feedback_text)
            if posts:
                source = f"Note: {note_file.stem}"
                append_to_log(f"{note_file.name}\t{today_str}\tline_notified")

    # --- 3. それでも空なら何もしない ---
    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # LINE送信
    message = build_line_message(posts, source, hook=hook, thread_body=thread_body)
    if send_line_message(line_token, line_user_id, message):
        append_to_log(f"rss\t{today_str}\tline_notified")
        print(f"[LINE通知完了] {source}")
    else:
        print("[LINE通知失敗]")
        sys.exit(1)


if __name__ == "__main__":
    main()
