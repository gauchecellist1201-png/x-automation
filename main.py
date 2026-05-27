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
    generate_thread_from_rss,
    score_tweet,
    suggest_image,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

DAILY_THEMES = [
    "📈 ビジネス×AI",
    "🏥 医療×AI",
    "🔬 テクノロジー最前線",
    "🌍 社会変革",
    "🛠 実践・活用術",
    "🔮 深掘り洞察",
    "📋 週まとめ",
]


def load_posted_log() -> set[str]:
    if not LOG_FILE.exists():
        return set()
    posted: set[str] = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        filename = line.split("\t")[0]
        posted.add(filename)
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
    # LINE テキストメッセージ上限 5000 文字
    text = message[:4900] if len(message) > 4900 else message
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}],
    }
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    return response.status_code == 200


def build_line_message(posts: list[str], source: str) -> str:
    today = date.today()
    date_str = today.strftime("%Y/%m/%d")
    theme = DAILY_THEMES[today.weekday()]

    lines = [
        f"🤖 X投稿案 {date_str}【{theme}】",
        f"📡 ソース: {source}",
        "━" * 22,
    ]

    # スコア降順でソート
    scored = sorted(
        [(p, score_tweet(p)) for p in posts[:3]],
        key=lambda x: x[1],
        reverse=True,
    )

    medals = ["🥇", "🥈", "🥉"]
    for i, (post, sc) in enumerate(scored):
        lines.append(f"\n{medals[i]} 案{i + 1}（スコア: {sc}/100）")
        lines.append("─" * 20)
        lines.append(post)
        lines.append("─" * 20)
        if i == 0:
            lines.append(f"🖼 推奨画像: {suggest_image(post)}")

    lines.append("\n💡 気に入った案をコピーしてXに投稿！")
    lines.append("📝 反応が良かったら data/feedback.txt に追記してください")
    return "\n".join(lines)


def build_thread_message(thread_tweets: list[str]) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🧵 スレッド投稿案 {today}【木曜: 社会変革】",
        "━" * 22,
        "（下記を順番に投稿 → 2〜4は1ツイート目に返信）",
        "",
    ]
    for i, tweet in enumerate(thread_tweets, 1):
        lines.append(f"【{i}/{len(thread_tweets)}】")
        lines.append(tweet)
        lines.append("")
    lines.append("💡 1/4を投稿後、そのツイートに返信する形で続けてください")
    return "\n".join(lines)


def _extract_note_url(note_text: str) -> str:
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split(":", 1)[1].strip()
    return ""


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # Note記事から生成（未使用のものを優先）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_url = _extract_note_url(note_text)
        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            message = build_line_message(posts, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # 木曜日はスレッド形式で配信
    if date.today().weekday() == 3:
        thread_tweets = generate_thread_from_rss()
        if thread_tweets:
            message = build_thread_message(thread_tweets)
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"rss_thread\t{date.today()}\tline_notified")
                print("[LINE通知完了] RSSスレッド")
                return

    # RSS最新ニュースから生成
    posts = generate_posts_from_rss()
    if posts:
        message = build_line_message(posts, "最新AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
