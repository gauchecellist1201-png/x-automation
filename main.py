"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
バズ分析 + スレッド投稿 + ニュースURL付き通知版
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss, generate_thread_post

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


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


def build_line_message(
    posts: list[str],
    source: str,
    thread: list[str] | None = None,
    source_url: str = "",
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🤖 今日({today})のX投稿案 [{source}]",
        "━" * 22,
        "",
        "【通常ツイート案】",
    ]

    for i, post in enumerate(posts[:3], 1):
        lines.append(f"▼ 案{i}")
        lines.append(post)
        lines.append("")

    if source_url:
        lines.append(f"📰 参考ニュース（OGP画像付きで貼ると◎）")
        lines.append(source_url)
        lines.append("")

    if thread:
        lines.append("━" * 22)
        lines.append("【スレッド投稿案 ※エンゲージ3〜5倍】")
        for i, part in enumerate(thread, 1):
            lines.append(f"[{i}/{len(thread)}] {part}")
            lines.append("")

    lines.append("━" * 22)
    lines.append("✅ 気に入った案をコピーしてXに投稿！")
    lines.append("💡 画像はニュースURLのOGPか、図解スクショが効果的")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    source_url = ""
    thread: list[str] = []

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # Note内URLがあれば抽出
        import re
        url_match = re.search(r"NOTE_URL:\s*(\S+)", note_text)
        note_url = url_match.group(1) if url_match else ""

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            thread = generate_thread_post(note_text[:200])
            message = build_line_message(
                posts,
                f"Note: {note_file.stem}",
                thread=thread,
                source_url=note_url,
            )
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    posts, source_url = generate_posts_from_rss()
    if posts:
        thread = generate_thread_post(posts[0][:80] if posts else "")
        message = build_line_message(
            posts,
            "AIニュース",
            thread=thread,
            source_url=source_url,
        )
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
