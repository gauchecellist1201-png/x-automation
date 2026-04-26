"""
毎日 JST 21:00 にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import (
    TweetCandidate,
    generate_posts_from_notes,
    generate_posts_from_rss,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

SCORE_LABELS = {
    range(9, 11): "🔥🔥🔥 超バズ候補",
    range(7, 9):  "🔥🔥 バズ候補",
    range(5, 7):  "🔥 良質",
    range(0, 5):  "📝 普通",
}


def _score_label(score: int) -> str:
    for r, label in SCORE_LABELS.items():
        if score in r:
            return label
    return "📝"


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


def build_line_message(candidates: list[TweetCandidate], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🤖 今日({today})のX投稿案 [{source}]",
        "━" * 22,
    ]

    for i, c in enumerate(candidates[:3], 1):
        label = _score_label(c.buzz_score)
        lines.append(f"\n【案{i}】 {label} (スコア {c.buzz_score}/10)")
        lines.append(f"パターン: {c.viral_pattern}")
        if c.source_headline and c.source_headline != "（オリジナル洞察）":
            lines.append(f"元ネタ: {c.source_headline}")
        lines.append("")
        lines.append(c.text)
        if c.visual_hint:
            lines.append(f"\n📷 ビジュアル提案: {c.visual_hint}")
        if c.tags:
            lines.append(f"🏷 タグ: {' '.join(c.tags)}")
        lines.append("─" * 22)

    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💡 スコアが高い案ほどバズりやすい予測です")
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

        # NOTE_URL を本文から抽出
        note_url_match = __import__("re").search(r"NOTE_URL:\s*(https?://\S+)", note_text)
        note_url = note_url_match.group(1) if note_url_match else ""

        candidates = generate_posts_from_notes(note_text, feedback_text, note_url)
        if candidates:
            message = build_line_message(candidates, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name} ({len(candidates)}案)")
                return

    # RSSニュースから生成
    candidates = generate_posts_from_rss()
    if candidates:
        message = build_line_message(candidates, "AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print(f"[LINE通知完了] RSSニュース ({len(candidates)}案)")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
