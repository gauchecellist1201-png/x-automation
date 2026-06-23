"""
毎日21:00 JST にAI投稿を自動生成・X投稿・LINE通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss
from tweet_poster import post_tweet, has_x_credentials

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> set[str]:
    if not LOG_FILE.exists():
        return set()
    posted = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
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
    all_notes = list(NOTES_DIR.glob("*.md"))
    unposted = [p for p in all_notes if p.name not in posted]
    # 全て使用済みなら全ノートから再選択（ローテーション）
    return unposted if unposted else all_notes


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


def build_line_message_posted(posted_text: str, alternatives: list[str], tweet_id: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    tweet_url = f"https://x.com/i/web/status/{tweet_id}"
    lines = [
        f"\n✅ 今日({today})のX投稿完了 [{source}]",
        f"🔗 {tweet_url}",
        "─" * 20,
        f"\n【投稿内容】\n{posted_text}",
        "─" * 20,
    ]
    if alternatives:
        lines.append("\n📝 ボツ案（次回参考に）")
        for i, alt in enumerate(alternatives[:2], 1):
            lines.append(f"\n【案{i+1}】\n{alt}")
    return "\n".join(lines)


def build_line_message_candidates(posts: list[str], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "⚠️ X API未設定のため手動投稿が必要です",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)
    source = "AIニュース"
    posts: list[str] = []

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            source = f"Note: {note_file.stem}"

    # Note生成失敗 or ノートなし → RSSから生成
    if not posts:
        posts = generate_posts_from_rss()

    if not posts:
        print("投稿候補が生成できませんでした。")
        sys.exit(1)

    best_post = posts[0]
    alternatives = posts[1:]

    # X API直接投稿
    tweet_id = None
    if has_x_credentials():
        tweet_id = post_tweet(best_post)

    # LINE通知
    if tweet_id:
        message = build_line_message_posted(best_post, alternatives, tweet_id, source)
        log_status = f"x_posted\t{tweet_id}"
    else:
        message = build_line_message_candidates(posts, source)
        log_status = "line_notified"

    if send_line_message(line_token, line_user_id, message):
        # 使ったソースをログに記録
        log_key = source.replace("Note: ", "") + ".md" if source.startswith("Note:") else "rss"
        if source.startswith("Note:"):
            note_stem = source.replace("Note: ", "")
            log_key = f"{note_stem}.md"
        else:
            log_key = "rss"
        append_to_log(f"{log_key}\t{date.today()}\t{log_status}")
        print(f"[完了] source={source}, status={log_status}")
    else:
        print("[LINE通知失敗]")
        sys.exit(1)


if __name__ == "__main__":
    main()
