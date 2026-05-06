"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date, timedelta
from content_gen import generate_posts_from_notes, generate_posts_from_rss, suggest_images

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")
NOTE_COOLDOWN_DAYS = 14  # 同じnoteを再利用するまでの間隔

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> dict[str, list[date]]:
    """ログをパースしてファイル名 -> [投稿日付リスト] を返す"""
    if not LOG_FILE.exists():
        return {}
    result: dict[str, list[date]] = {}
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        filename = parts[0]
        try:
            posted_date = date.fromisoformat(parts[1])
        except ValueError:
            continue
        result.setdefault(filename, []).append(posted_date)
    return result


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_available_notes(log: dict[str, list[date]]) -> list[Path]:
    """クールダウン期間を過ぎたnoteファイルを返す"""
    if not NOTES_DIR.exists():
        return []
    today = date.today()
    available = []
    for p in NOTES_DIR.glob("*.md"):
        past_dates = log.get(p.name, [])
        if not past_dates:
            available.append(p)
        elif (today - max(past_dates)).days >= NOTE_COOLDOWN_DAYS:
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
    try:
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"LINE送信エラー: {e}")
        return False


def build_line_message(posts: list[str], source: str, image_hints: list[str] | None = None) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🤖 今日({today})のX投稿案",
        f"📌 ソース: {source}",
        "━" * 18,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】")
        lines.append(post)
        if image_hints and i <= len(image_hints):
            lines.append(f"🖼️ 画像: {image_hints[i - 1]}")
        lines.append("─" * 14)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿！")
    lines.append("📷 画像はUnsplash/Pixabayで上記キーワード検索")
    return "\n".join(lines)


def extract_note_url(note_text: str) -> str:
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split("NOTE_URL:", 1)[1].strip()
    return ""


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    log = load_posted_log()
    available_notes = get_available_notes(log)

    # Note記事から生成（クールダウン期間を過ぎたものが対象）
    if available_notes:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_url = extract_note_url(note_text)

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            image_hints = suggest_images(posts)
            message = build_line_message(posts, f"Note: {note_file.stem}", image_hints)
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    posts = generate_posts_from_rss()
    if posts:
        image_hints = suggest_images(posts)
        message = build_line_message(posts, "AIニュース", image_hints)
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
