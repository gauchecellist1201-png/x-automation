"""
毎日21:00 JST にビジネス向けバイラルAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss

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


def _char_count(text: str) -> int:
    """ツイート文字数をカウント（URLは23文字換算）"""
    import re
    url_pattern = re.compile(r"https?://\S+")
    urls = url_pattern.findall(text)
    count = len(text)
    for url in urls:
        count = count - len(url) + 23
    return count


def build_line_message(posts: list[dict], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    sep = "━" * 22

    lines = [
        f"🤖 今日({today})のX投稿案",
        f"📌 ソース: {source}",
        sep,
    ]

    # ニュース元タイトルを1回だけ表示
    if posts and posts[0].get("source_title"):
        source_title = posts[0]["source_title"]
        if source_title not in ("Note記事", "AIビジネス洞察"):
            lines.append(f"📰 元ネタ: {source_title[:60]}{'…' if len(source_title) > 60 else ''}")
            lines.append(sep)

    for i, post in enumerate(posts[:3], 1):
        tweet = post["tweet"]
        pattern_name = post.get("pattern_name", "")
        image_hint = post.get("image_hint", "")
        source_url = post.get("source_url", "")
        char_count = _char_count(tweet)

        lines.append(f"\n【案{i}】{pattern_name} ({char_count}文字)")
        lines.append(tweet)
        if source_url:
            lines.append(f"🔗 {source_url}")
        lines.append(f"📸 推奨画像: {image_hint}")
        lines.append(sep)

    lines.append("\n✅ 気に入った案をXに投稿してください！")
    lines.append("📊 エンゲージメント後は feedback.txt に追記でAIが学習します")
    return "\n".join(lines)


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
            message = build_line_message(posts, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    posts = generate_posts_from_rss()
    if posts:
        source_title = posts[0].get("source_title", "AIニュース")
        message = build_line_message(posts, source_title[:40])
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
