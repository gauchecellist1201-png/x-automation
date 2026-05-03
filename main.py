"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss
from trend_analyzer import get_today_strategy

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
    if response.status_code != 200:
        print(f"[LINE ERROR] {response.status_code}: {response.text}")
    return response.status_code == 200


def build_line_message_from_notes(posts: list[str], source_name: str, note_url: str = "") -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"📝 今日({today})のX投稿案",
        f"📌 元ネタ: {source_name}",
        "━" * 22,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        char_count = len(post)
        lines.append(f"（{char_count}文字）")
        lines.append("─" * 20)

    if note_url:
        lines.append(f"\n🔗 Note記事: {note_url}")

    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💬 反応が良かったものは data/feedback.txt に追記してください")
    return "\n".join(lines)


def build_line_message_from_rss(post_items: list[dict], strategy: dict) -> str:
    today = date.today().strftime("%Y/%m/%d")
    analysis = strategy.get("analysis", {})
    topic = analysis.get("topic", "最新AIトレンド")
    why_viral = analysis.get("why_viral", "")
    recommended_fmt = strategy.get("recommended_format", "")
    fmt_template = strategy.get("format_template", "")

    lines = [
        f"🤖 今日({today})のX投稿案",
        f"🔥 今日のホットトピック: {topic}",
    ]
    if why_viral:
        lines.append(f"💡 バズりやすい理由: {why_viral}")
    lines.append("━" * 22)

    for i, item in enumerate(post_items[:3], 1):
        tweet = item.get("tweet", "")
        source_title = item.get("source_title", "")
        source_link = item.get("source_link", "")

        lines.append(f"\n【案{i}】\n{tweet}")
        char_count = len(tweet)
        lines.append(f"（{char_count}文字）")

        if source_title and i == 1:
            src_line = f"📰 参照: {source_title}"
            if source_link:
                src_line += f"\n🔗 {source_link}"
            lines.append(src_line)
        lines.append("─" * 20)

    if fmt_template:
        lines.append(f"\n📋 今日の推奨フォーマット:\n{fmt_template}")

    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💬 反応が良かったものは data/feedback.txt に追記してください")
    return "\n".join(lines)


def build_line_message_thread(thread_posts: list[str], topic: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🧵 今日({today})のスレッド投稿案",
        f"📌 テーマ: {topic}",
        "━" * 22,
        "\n【このまま3連投稿できます】",
    ]
    for i, post in enumerate(thread_posts, 1):
        lines.append(f"\n{i}/{len(thread_posts)}:\n{post}")
        lines.append(f"（{len(post)}文字）")
        lines.append("─" * 20)

    lines.append("\n✅ 上から順に投稿してスレッドにしてください！")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # トレンド分析（バックグラウンドで取得）
    print("[トレンド分析中...]")
    try:
        strategy = get_today_strategy()
        topic = strategy["analysis"].get("topic", "最新AIトレンド")
        print(f"[今日のホットトピック] {topic}")
    except Exception as e:
        print(f"[トレンド分析エラー] {e}")
        strategy = {"analysis": {}, "recommended_format": "", "format_template": "", "all_headlines": []}

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # Note URLを抽出
        note_url = ""
        for line in note_text.splitlines():
            if "NOTE_URL:" in line:
                note_url = line.split("NOTE_URL:")[-1].strip()
                break

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            message = build_line_message_from_notes(posts, note_file.stem, note_url)
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    print("[RSSニュースから投稿生成中...]")
    post_items = generate_posts_from_rss()
    if post_items:
        message = build_line_message_from_rss(post_items, strategy)
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
