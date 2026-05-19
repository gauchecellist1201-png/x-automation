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
    generate_thread_post,
    generate_original_ai_insight,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_notes() -> set[str]:
    """ログからすでに通知済みのノートファイル名セットを返す"""
    if not LOG_FILE.exists():
        return set()
    posted: set[str] = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if parts:
            posted.add(parts[0])
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
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=15)
    return response.status_code == 200


def build_line_message(posts: list[str], source: str, is_thread: bool = False) -> str:
    today = date.today().strftime("%Y/%m/%d")
    mode = "🧵 スレッド投稿案" if is_thread else "📢 X投稿案"
    lines = [
        f"\n🤖 今日({today})の{mode} [{source}]",
        "─" * 22,
    ]
    label = "ツイート" if is_thread else "案"
    for i, post in enumerate(posts, 1):
        lines.append(f"\n【{label}{i}】\n{post}")
        lines.append("─" * 22)
    if is_thread:
        lines.append("\n🧵 1→5の順番でそのまま投稿するとスレッドになります！")
    else:
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
        lines.append("💡 複数案を組み合わせてもOKです。")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_notes()
    unposted = get_unposted_notes(posted)

    # 月曜・木曜はスレッド投稿（エンゲージメント最大化）
    today_weekday = date.today().weekday()  # 0=月, 3=木
    if today_weekday in (0, 3):
        posts = generate_thread_post()
        if posts:
            message = build_line_message(posts, "スレッド形式", is_thread=True)
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"thread\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] スレッド投稿案")
                return

    # Note記事から生成（未投稿のものがあれば優先）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        # NOTE_URL を記事内から抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split(":", 1)[1].strip()
                break
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
        message = build_line_message(posts, "最新AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    # フォールバック: オリジナル洞察
    posts = generate_original_ai_insight()
    if posts:
        message = build_line_message(posts, "オリジナル洞察")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"original\t{date.today()}\tline_notified")
            print("[LINE通知完了] オリジナル洞察")
            return

    print("投稿候補が生成できませんでした。")
    sys.exit(1)


if __name__ == "__main__":
    main()
