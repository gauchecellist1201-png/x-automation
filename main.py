"""
毎日 JST 8:00 / 21:00 にAI投稿案を生成してLINEに通知するスクリプト
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
    generate_thread,
    TweetCandidate,
)

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


def extract_note_url(note_text: str) -> str:
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split(":", 1)[1].strip()
    return ""


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


def build_line_message(candidates: list[TweetCandidate], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    sorted_candidates = sorted(candidates, key=lambda c: c["virality_score"], reverse=True)
    lines = [f"\n AI投稿案 ({today}) [{source}]", "─" * 22]
    for i, c in enumerate(sorted_candidates[:3], 1):
        stars = "★" * c["virality_score"] + "☆" * (10 - c["virality_score"])
        lines.append(f"\n【案{i}】スコア {c['virality_score']}/10  {stars}")
        if c["pattern"]:
            lines.append(f"パターン: {c['pattern']}")
        lines.append(f"\n{c['text']}")
        if c["image_prompt"]:
            lines.append(f"\n📸 画像案: {c['image_prompt']}")
        lines.append("─" * 22)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿！")
    return "\n".join(lines)


def build_thread_message(tweets: list[str], topic: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🧵 スレッド案 ({today}) [{topic}]", "─" * 22]
    for i, tweet in enumerate(tweets, 1):
        label = "🔹 1/" if i == 1 else f"🔸 {i}/"
        lines.append(f"\n{label}\n{tweet}")
    lines.append("\n─" * 22)
    lines.append("✅ 上から順に連続投稿してください！")
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
        note_url = extract_note_url(note_text)

        candidates = generate_posts_from_notes(note_text, feedback_text, note_url)
        if candidates:
            message = build_line_message(candidates, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")

            # スレッドも生成して通知
            best = max(candidates, key=lambda c: c["virality_score"])
            thread = generate_thread(best["text"], note_url)
            if thread:
                thread_msg = build_thread_message(thread, note_file.stem)
                if send_line_message(line_token, line_user_id, thread_msg):
                    print(f"[LINE通知完了] スレッド: {note_file.name}")
            return

    # RSSニュースから生成
    candidates = generate_posts_from_rss()
    if candidates:
        message = build_line_message(candidates, "AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース（単体ツイート）")

        # 最高スコアのトピックでスレッドも生成
        best = max(candidates, key=lambda c: c["virality_score"])
        thread = generate_thread(best["text"])
        if thread:
            thread_msg = build_thread_message(thread, "AIニュース")
            if send_line_message(line_token, line_user_id, thread_msg):
                print("[LINE通知完了] RSSニュース（スレッド）")
        return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
