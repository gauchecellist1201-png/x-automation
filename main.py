"""
毎日 JST 21:00 に実行されるAI投稿自動化スクリプト

フロー:
  1. バズりパターンを取得（X API or フォールバック）
  2. Note記事 or RSSニュースから投稿候補を3案生成
  3. Claude がベスト案を自動選択
  4. X に自動投稿
  5. LINE に投稿結果 + 全候補を通知
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
    select_best_tweet,
)
from x_poster import post_tweet, tweet_url

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


# ---- ユーティリティ -----------------------------------------------------------

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


# ---- LINE 通知 ---------------------------------------------------------------

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


def build_line_message(
    posted_text: str,
    posted_id: str | None,
    all_candidates: list[str],
    source: str,
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    url = tweet_url(posted_id) if posted_id else "投稿失敗"

    lines = [
        f"\n🚀 今日({today})のX投稿 [{source}]",
        "─" * 24,
        "\n✅【自動投稿済み】",
        posted_text,
        f"\n🔗 {url}",
        "\n─" * 24,
        "\n📋 その他の候補",
    ]
    for i, candidate in enumerate(all_candidates, 1):
        if candidate != posted_text:
            lines.append(f"\n【案{i}】\n{candidate}")

    return "\n".join(lines)


# ---- メイン ------------------------------------------------------------------

def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    posted_log = load_posted_log()
    unposted_notes = get_unposted_notes(posted_log)

    candidates: list[str] = []
    source = "AIニュース"

    # Note 記事から生成（未投稿のものが残っていれば優先）
    if unposted_notes:
        note_file = random.choice(unposted_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # naoki_profile.md の NOTE_URL を抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split(":", 1)[1].strip()

        candidates = generate_posts_from_notes(note_text, feedback_text, note_url)
        if candidates:
            source = f"Note: {note_file.stem}"

    # RSS ニュースから生成（fallback）
    if not candidates:
        candidates = generate_posts_from_rss()

    if not candidates:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # ベスト案を自動選択して X に投稿
    best = select_best_tweet(candidates)
    tweet_id = post_tweet(best)

    if tweet_id:
        print(f"[X投稿完了] {tweet_url(tweet_id)}")
        append_to_log(f"{source}\t{date.today()}\t{tweet_id}")
    else:
        print("[X投稿失敗] APIエラーが発生しました")

    # LINE 通知（token があれば）
    if line_token and line_user_id:
        message = build_line_message(best, tweet_id, candidates, source)
        ok = send_line_message(line_token, line_user_id, message)
        print("[LINE通知完了]" if ok else "[LINE通知失敗]")


if __name__ == "__main__":
    main()
