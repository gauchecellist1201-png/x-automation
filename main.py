"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import PostContent, generate_posts_from_notes, generate_posts_from_rss

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_filenames() -> set[str]:
    """ログから投稿済みファイル名のみ抽出（タブ区切りの1列目）"""
    if not LOG_FILE.exists():
        return set()
    filenames = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            filenames.add(line.split("\t")[0])
    return filenames


def append_to_log(filename: str, status: str = "line_notified") -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{filename}\t{date.today()}\t{status}\n")


def get_unposted_notes(posted_filenames: set[str]) -> list[Path]:
    """まだ投稿していないノートファイルを返す"""
    if not NOTES_DIR.exists():
        return []
    return [p for p in NOTES_DIR.glob("*.md") if p.name not in posted_filenames]


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


def build_line_message(content: PostContent, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    sep = "─" * 22
    lines = [f"\n🤖 今日({today})のX投稿案 [{source}]", sep]

    # シングルツイート候補
    if content.tweets:
        lines.append("\n【📝 シングルツイート候補】")
        for i, tweet in enumerate(content.tweets[:3], 1):
            lines.append(f"\n▶ 案{i}\n{tweet}")
            lines.append(sep)

    # スレッド案
    if content.thread:
        lines.append("\n【🧵 スレッド案（高エンゲージメント）】")
        for tweet in content.thread:
            lines.append(f"\n{tweet}")
        lines.append(sep)

    # 参照記事
    if content.source_title:
        lines.append(f"\n📰 参照: {content.source_title}")
    if content.source_url:
        lines.append(f"🔗 {content.source_url}")

    # 画像プロンプト
    if content.image_prompt:
        lines.append(f"\n{content.image_prompt}")
        lines.append("（Canva / Adobe Firefly / DALL-E で作成推奨）")

    lines.append(sep)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💡 スレッドは1ツイート目を投稿後、返信で続けてください。")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_filenames()
    unposted = get_unposted_notes(posted)

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # NOTE_URL をノート本文から抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.replace("NOTE_URL:", "").strip()
                break

        content = generate_posts_from_notes(note_text, feedback_text, note_url)
        if content.tweets or content.thread:
            message = build_line_message(content, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(note_file.name)
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    content = generate_posts_from_rss()
    if content.tweets or content.thread:
        message = build_line_message(content, "AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log("rss")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
