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
    generate_image_suggestion,
    generate_thread_posts,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

NOTE_COOLDOWN_DAYS = 14  # 同じNoteを再利用するまでの待機日数


def load_posted_log() -> dict[str, date]:
    """ファイル名 → 最後の投稿日 を返す（タブ区切りログを正しくパース）"""
    if not LOG_FILE.exists():
        return {}
    last_posted: dict[str, date] = {}
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        filename, date_str = parts[0], parts[1]
        try:
            post_date = date.fromisoformat(date_str)
            if filename not in last_posted or post_date > last_posted[filename]:
                last_posted[filename] = post_date
        except ValueError:
            pass
    return last_posted


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_available_notes(last_posted: dict[str, date]) -> list[Path]:
    """未投稿 or NOTE_COOLDOWN_DAYS 日以上前に投稿済みのNoteを返す"""
    if not NOTES_DIR.exists():
        return []
    cooldown = timedelta(days=NOTE_COOLDOWN_DAYS)
    today = date.today()
    return [
        p for p in NOTES_DIR.glob("*.md")
        if p.name not in last_posted
        or (today - last_posted[p.name]) >= cooldown
    ]


def extract_note_url(note_text: str) -> str:
    """Note本文から NOTE_URL: を抽出"""
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split(":", 1)[1].strip()
    return ""


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


def build_line_message(posts: list[str], source: str, image_hint: str = "") -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n今日({today})のX投稿案 [{source}]",
        "─" * 22,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        if i == 1 and image_hint:
            lines.append(f"📷 {image_hint}")
        lines.append("─" * 22)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("🧵 スレッド版は次のメッセージで届きます")
    return "\n".join(lines)


def send_thread_message(token: str, user_id: str, thread: list[str]) -> None:
    """スレッド投稿案を別メッセージで送信"""
    if not thread:
        return
    lines = ["\n🧵 スレッド版（より深い内容・高エンゲージメント）", "─" * 22]
    for i, tweet in enumerate(thread, 1):
        lines.append(f"\n[{i}/{len(thread)}]\n{tweet}")
    lines.append("\n─" * 22)
    lines.append("✅ 上記を順番に連続投稿するとスレッドになります")
    send_line_message(token, user_id, "\n".join(lines))


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    last_posted = load_posted_log()
    available_notes = get_available_notes(last_posted)

    note_url = ""

    # Note記事から生成
    if available_notes:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_url = extract_note_url(note_text)
        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        source = f"Note: {note_file.stem}"
    else:
        posts = generate_posts_from_rss()
        source = "AIニュース"

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # 画像提案（トップ投稿のみ）
    image_hint = ""
    try:
        image_hint = generate_image_suggestion(posts[0])
    except Exception as e:
        print(f"[画像提案スキップ] {e}")

    message = build_line_message(posts, source, image_hint)
    if send_line_message(line_token, line_user_id, message):
        log_key = note_file.name if available_notes else "rss"
        append_to_log(f"{log_key}\t{date.today()}\tline_notified")
        print(f"[LINE通知完了] {source}")

        # スレッド版を別メッセージで送信
        try:
            thread = generate_thread_posts(posts[0], note_url)
            send_thread_message(line_token, line_user_id, thread)
            print("[スレッド送信完了]")
        except Exception as e:
            print(f"[スレッド生成スキップ] {e}")
    else:
        print("[LINE送信失敗]")
        sys.exit(1)


if __name__ == "__main__":
    main()
