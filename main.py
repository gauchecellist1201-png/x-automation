"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
バズる投稿パターン × スレッド生成 × 画像提案対応版
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
    generate_viral_thread,
    suggest_image,
    fetch_rss_items,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_MAX_CHARS = 4800


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
    image_hint: str = "",
    source_url: str = "",
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    sep = "─" * 20
    bold_sep = "━" * 20

    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        bold_sep,
    ]

    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append(sep)

    if image_hint:
        lines.append(f"\n📸 画像提案: {image_hint}")
        lines.append(sep)

    if source_url:
        lines.append(f"\n🔗 ソース記事: {source_url}")
        lines.append(sep)

    if thread:
        lines.append(f"\n{bold_sep}")
        lines.append("🧵【スレッド案】")
        for j, t in enumerate(thread, 1):
            lines.append(f"\n[{j}/{len(thread)}] {t}")
        lines.append(bold_sep)

    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    msg = "\n".join(lines)

    if len(msg) > LINE_MAX_CHARS:
        msg = msg[:LINE_MAX_CHARS - 3] + "..."

    return msg


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            thread = generate_viral_thread(note_file.stem, note_text)
            image_hint = suggest_image(posts[0])
            message = build_line_message(
                posts,
                f"Note: {note_file.stem}",
                thread=thread,
                image_hint=image_hint,
            )
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    rss_items = fetch_rss_items(max_items=5)
    posts = generate_posts_from_rss()
    if posts:
        top_url = rss_items[0]["link"] if rss_items else ""
        thread_topic = rss_items[0]["title"] if rss_items else "最新AI動向"
        thread_detail = "\n".join(item["title"] for item in rss_items)
        thread = generate_viral_thread(thread_topic, thread_detail)
        image_hint = suggest_image(posts[0])
        message = build_line_message(
            posts,
            "AIニュース",
            thread=thread,
            image_hint=image_hint,
            source_url=top_url,
        )
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
