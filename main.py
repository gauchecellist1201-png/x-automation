"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
曜日別バズりフォーマット戦略でビジネス層向けコンテンツを毎日5案提案
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_viral_posts, get_today_format

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> set[str]:
    """ログからファイル名だけを抽出して返す"""
    if not LOG_FILE.exists():
        return set()
    posted = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if parts:
            posted.add(parts[0].strip())
    return posted


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
    except requests.RequestException:
        return False


def build_line_message(posts: list[str], source: str, theme: str) -> str:
    today = date.today().strftime("%Y/%m/%d (%a)")
    divider = "─" * 22
    lines = [
        f"AI投稿案 {today}",
        f"テーマ: {theme}",
        f"ソース: {source}",
        divider,
    ]
    for i, post in enumerate(posts[:5], 1):
        char_count = len(post)
        lines.append(f"\n案{i} ({char_count}文字)")
        lines.append(post)
        lines.append(divider)
    lines.append("\n気に入った案をそのままコピーしてXへ！")
    lines.append("ハッシュタグ追加や文言調整もお忘れなく")
    return "\n".join(lines)


def extract_note_url(note_text: str) -> str:
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split(":", 1)[1].strip()
    return ""


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
    format_key, theme_label = get_today_format()

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # Note記事から生成（未使用のファイルがある場合）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        note_url = extract_note_url(note_text)

        posts, theme = generate_viral_posts(
            format_key=format_key,
            note_text=note_text,
            feedback_text=feedback_text,
            note_url=note_url,
        )
        if posts:
            message = build_line_message(posts, f"Note: {note_file.stem}", theme)
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name} / テーマ: {theme}")
                return

    # RSSニュースから生成
    posts, theme = generate_viral_posts(
        format_key=format_key,
        feedback_text=feedback_text,
    )
    if posts:
        message = build_line_message(posts, "最新AIニュース", theme)
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print(f"[LINE通知完了] RSSニュース / テーマ: {theme}")
            return

    print("投稿候補がありませんでした。")
    sys.exit(1)


if __name__ == "__main__":
    main()
