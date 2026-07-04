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
    generate_thread_opener,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

THREAD_TOPICS = [
    "ChatGPTのシェアが初めて50%を割った。Claudeが855%成長している今、AIスタック選定はどう変わるか",
    "医師がコードを書かずに医療AIプロダクトを作れる時代。医療×AIの民主化が意味すること",
    "AIエージェントが「デモ映え」から「実務完遂」フェーズへ。ビジネスで本当に使えるAIとは",
    "国連がAIガバナンス会議を開幕。医療データ×AI×ブロックチェーンに何が起きるか",
    "GPT-5.6、Gemini 3.5 Pro、Claude Fable 5——2026年下半期のAIモデル戦争の行方",
]


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


def build_line_message(posts: list[str], source: str, thread_posts: list[str] | None = None) -> str:
    today = date.today().strftime("%Y/%m/%d")
    char_counts = [f"{len(p)}字" for p in posts[:3]]
    lines = [
        f"🤖 今日({today})のX投稿案 [{source}]",
        "━" * 22,
    ]
    for i, (post, count) in enumerate(zip(posts[:3], char_counts), 1):
        lines.append(f"\n【案{i}】（{count}）\n{post}")
        lines.append("─" * 22)

    if thread_posts:
        lines.append("\n🧵 スレッド冒頭案（連ツイ用）")
        lines.append("─" * 22)
        for i, post in enumerate(thread_posts[:2], 1):
            lines.append(f"\n【スレ{i}】（{len(post)}字）\n{post}")
            lines.append("─" * 22)

    lines.append(
        "\n✅ 気に入った案をコピーしてXに投稿！\n"
        "💡 返信を呼ぶ投稿が最もリーチが伸びます"
    )
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # スレッド冒頭案を常に生成（サブコンテンツとして添付）
    thread_topic = random.choice(THREAD_TOPICS)
    thread_posts = generate_thread_opener(thread_topic)

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            message = build_line_message(posts, f"Note: {note_file.stem}", thread_posts)
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    posts = generate_posts_from_rss()
    if posts:
        message = build_line_message(posts, "AIニュース", thread_posts)
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
