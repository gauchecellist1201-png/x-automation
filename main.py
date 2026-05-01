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
    generate_image_prompt,
    fetch_rss_headlines,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_MAX_CHARS = 5000  # LINE Messaging API の1メッセージ上限


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
    # プロフィールファイルはNote記事ではないので除外
    excluded = {"naoki_profile.md"}
    return [
        p for p in NOTES_DIR.glob("*.md")
        if p.name not in posted and p.name not in excluded
    ]


def send_line_message(token: str, user_id: str, message: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message[:LINE_MAX_CHARS]}],
    }
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"[LINE ERROR] {response.status_code}: {response.text}")
    return response.status_code == 200


def build_line_message(
    posts: list[str],
    source: str,
    thread_text: str = "",
    image_prompt: str = "",
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    sep = "─" * 22

    lines = [
        f"🤖 今日({today})のX投稿案",
        f"📰 ソース: {source}",
        sep,
    ]

    # 単ツイート候補
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append(sep)

    # スレッド案
    if thread_text:
        lines.append("\n🧵【スレッド案（高エンゲージメント狙い）】")
        lines.append(sep)
        lines.append(thread_text[:800])
        lines.append(sep)

    # 画像プロンプト
    if image_prompt:
        lines.append("\n🖼 【画像生成プロンプト（DALL-E/Midjourney用）】")
        lines.append(image_prompt[:400])
        lines.append(sep)

    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💡 スレッドは複数ツイートに分割してそのまま使えます")

    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = ""
    thread_text = ""
    image_prompt = ""

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # NoteのURLを抽出（ファイル内に "NOTE_URL:" という行がある場合）
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.replace("NOTE_URL:", "").strip()
                break

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            source = f"Note: {note_file.stem}"
            # スレッド案生成（Note記事の最初の200文字をトピックに）
            topic = note_text[:200]
            thread_text = generate_thread_post(topic)
            image_prompt = generate_image_prompt(posts[0])
            append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")

    # RSSニュースから生成（Noteがなかった場合）
    if not posts:
        headlines = fetch_rss_headlines()
        posts = generate_posts_from_rss()
        if posts:
            source = "最新AIニュース"
            topic = headlines[0] if headlines else "AI最新トレンド2026"
            thread_text = generate_thread_post(topic, headlines)
            image_prompt = generate_image_prompt(posts[0])
            append_to_log(f"rss\t{date.today()}\tline_notified")

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    message = build_line_message(posts, source, thread_text, image_prompt)
    if send_line_message(line_token, line_user_id, message):
        print(f"[LINE通知完了] {source}")
    else:
        print("[LINE通知失敗]")
        sys.exit(1)


if __name__ == "__main__":
    main()
