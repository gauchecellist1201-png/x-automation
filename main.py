"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date, timedelta
from content_gen import generate_posts_from_notes, generate_posts_from_rss

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

# 同じNoteを再利用するまでの最低日数
NOTE_REUSE_DAYS = 14


def load_posted_log() -> list[dict]:
    """ログファイルを読み込み、{filename, date, status} のリストを返す"""
    if not LOG_FILE.exists():
        return []
    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            entries.append({"filename": parts[0], "date": parts[1], "status": parts[2] if len(parts) > 2 else ""})
    return entries


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_available_notes(log_entries: list[dict]) -> list[Path]:
    """NOTE_REUSE_DAYS日以上使っていないNoteを返す（古いものから優先）"""
    if not NOTES_DIR.exists():
        return []

    today = date.today()
    cutoff = today - timedelta(days=NOTE_REUSE_DAYS)

    # 各Noteファイルの最終使用日を集計
    last_used: dict[str, date] = {}
    for entry in log_entries:
        fname = entry["filename"]
        try:
            used_date = date.fromisoformat(entry["date"])
        except ValueError:
            continue
        if fname not in last_used or used_date > last_used[fname]:
            last_used[fname] = used_date

    available = []
    for p in NOTES_DIR.glob("*.md"):
        if p.name not in last_used or last_used[p.name] <= cutoff:
            available.append(p)

    # 最後に使った日が古い順でソート（未使用が先頭）
    available.sort(key=lambda p: last_used.get(p.name, date.min))
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


def build_line_message(posts: list[str], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💡 ヒント：返信を誘う質問で終わるものが拡散しやすいです")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    log_entries = load_posted_log()
    available_notes = get_available_notes(log_entries)

    # Note記事から生成（NOTE_REUSE_DAYS日以上未使用のもの）
    if available_notes:
        note_file = available_notes[0]  # 最も古いものを優先
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            message = build_line_message(posts, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    posts = generate_posts_from_rss()
    if posts:
        message = build_line_message(posts, "AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
