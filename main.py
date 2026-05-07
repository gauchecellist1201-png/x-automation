"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date

from content_gen import generate_posts_from_notes, generate_posts_from_rss, generate_image_prompt
from image_gen import generate_tweet_image

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


def _extract_note_url(note_text: str) -> str:
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split("NOTE_URL:", 1)[1].strip()
    return ""


def send_line_messages(token: str, user_id: str, messages: list[dict]) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"to": user_id, "messages": messages}
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"[LINE送信エラー] {response.status_code}: {response.text}")
    return response.status_code == 200


def build_posts_message(posts: list[str], source: str, article_url: str = "") -> dict:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🤖 今日({today})のX投稿案 [{source}]",
        "─" * 22,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 22)

    if article_url:
        lines.append(f"\n📰 元記事:\n{article_url}")
        lines.append("─" * 22)

    lines.append("\n✅ 気に入った案をコピーしてXに投稿！")
    lines.append("🖼️ 次のメッセージに投稿用画像URLがあります（1時間以内にDL）")

    return {"type": "text", "text": "\n".join(lines)}


def build_image_message(image_url: str, image_prompt: str) -> dict:
    text = (
        f"🖼️ 投稿用画像（⚠️約1時間で期限切れ）\n"
        f"{image_url}\n\n"
        f"📝 画像プロンプト:\n{image_prompt[:120]}"
    )
    return {"type": "text", "text": text}


def build_no_image_message() -> dict:
    return {"type": "text", "text": "🖼️ 画像生成をスキップしました（OPENAI_API_KEY未設定）"}


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    article_url = ""
    article_title = ""
    log_entry = ""
    source_label = ""

    # ① Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_url = _extract_note_url(note_text)

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            source_label = f"Note: {note_file.stem}"
            article_url = note_url
            log_entry = f"{note_file.name}\t{date.today()}\tline_notified"

    # ② RSSニュースから生成（Noteが無いか生成失敗時）
    if not posts:
        posts, article_title, article_url = generate_posts_from_rss()
        if posts:
            label = article_title[:20] + "…" if article_title else "最新AIニュース"
            source_label = f"AIニュース: {label}"
            log_entry = f"rss\t{date.today()}\tline_notified"

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # 投稿テキストメッセージを構築
    messages: list[dict] = [build_posts_message(posts, source_label, article_url)]

    # DALL-E 3 画像生成（投稿案1番を元にプロンプト作成）
    topic = article_title if article_title else "AI医療テクノロジービジネス"
    image_prompt = generate_image_prompt(posts[0], topic)
    image_url = generate_tweet_image(image_prompt)

    if image_url:
        messages.append(build_image_message(image_url, image_prompt))
    else:
        messages.append(build_no_image_message())

    # LINE送信（APIの上限は1回5メッセージ）
    if send_line_messages(line_token, line_user_id, messages[:5]):
        if log_entry:
            append_to_log(log_entry)
        print(f"[LINE通知完了] {len(messages)}件送信 | ソース: {source_label}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
