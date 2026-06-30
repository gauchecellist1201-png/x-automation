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
NOTE_COOLDOWN_DAYS = 14  # 同じNoteを再利用するまでの最低日数


def load_posted_log() -> dict[str, date]:
    """ログからファイル名→最終使用日のマッピングを返す（バグ修正版）"""
    result: dict[str, date] = {}
    if not LOG_FILE.exists():
        return result
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            filename = parts[0].strip()
            try:
                used_date = date.fromisoformat(parts[1].strip())
                # 最新の使用日を保持
                if filename not in result or used_date > result[filename]:
                    result[filename] = used_date
            except ValueError:
                continue
    return result


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_available_notes(log: dict[str, date]) -> list[Path]:
    """クールダウン期間を過ぎたノートファイルを返す"""
    if not NOTES_DIR.exists():
        return []
    today = date.today()
    available = []
    for p in NOTES_DIR.glob("*.md"):
        last_used = log.get(p.name)
        if last_used is None or (today - last_used).days >= NOTE_COOLDOWN_DAYS:
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


def build_line_message(posts: list[dict], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 22,
    ]
    for i, post in enumerate(posts[:3], 1):
        text = post.get("text", "")
        url = post.get("url", "")
        lines.append(f"\n【案{i}】\n{text}")
        if url:
            lines.append(f"📎 {url}")
        lines.append("─" * 22)
    lines.append("\n✅ 気に入った案をXに投稿してください！")
    lines.append("💡 URLも一緒にポストするとエンゲージメントUP")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    log = load_posted_log()
    available_notes = get_available_notes(log)

    # Note記事から生成（クールダウン済みのものをランダム選択）
    if available_notes:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # Note内のURLを抽出（NOTE_URL: https://... 形式）
        note_url = ""
        url_match = __import__("re").search(r"NOTE_URL:\s*(https?://\S+)", note_text)
        if url_match:
            note_url = url_match.group(1).strip()

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            message = build_line_message(posts, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    posts = generate_posts_from_rss()
    if posts:
        message = build_line_message(posts, "AIビジネスニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
