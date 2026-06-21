"""
毎日 JST 21:00 に最新AIニュースをもとにバズ投稿を生成し、X に自動投稿するスクリプト。
LINE には投稿済みツイートを確認通知として送る。
"""

import os
import re
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    select_best_tweet,
    fetch_article_image,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def get_used_today() -> set[str]:
    """今日すでに投稿済みのファイル名セット（当日の重複防止）"""
    if not LOG_FILE.exists():
        return set()
    today = str(date.today())
    used: set[str] = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1] == today:
                used.add(parts[0])
    return used


def append_to_log(filename: str, tweet_id: str) -> None:
    entry = f"{filename}\t{date.today()}\t{tweet_id}"
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_available_notes(used_today: set[str]) -> list[Path]:
    """当日未使用の Note ファイル一覧"""
    if not NOTES_DIR.exists():
        return []
    return [p for p in NOTES_DIR.glob("*.md") if p.name not in used_today]


def x_api_available() -> bool:
    return all(
        os.environ.get(k)
        for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    )


def line_available() -> bool:
    return bool(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN") and os.environ.get("LINE_USER_ID"))


def post_to_x(text: str, image_bytes: bytes | None = None) -> str:
    from tweet_poster import post_tweet
    return post_tweet(text, image_bytes)


def send_line_notification(token: str, user_id: str, message: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    resp = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    return resp.status_code == 200


def build_posted_notification(tweet: str, tweet_id: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    url = f"https://x.com/i/web/status/{tweet_id}"
    return (
        f"\n✅ X投稿完了！({today})\n"
        f"{'─' * 20}\n"
        f"{tweet}\n"
        f"{'─' * 20}\n"
        f"📎 {url}\n"
        f"📂 ソース: {source}"
    )


def build_draft_notification(candidates: list[str], source: str) -> str:
    """X API が未設定の場合、手動投稿用の下書き通知を作成"""
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🤖 今日({today})のX投稿案 [{source}]", "─" * 20]
    for i, post in enumerate(candidates[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def main() -> None:
    used_today = get_used_today()
    available_notes = get_available_notes(used_today)

    tweet: str = ""
    image_bytes: bytes | None = None
    source: str = ""
    log_key: str = ""
    all_candidates: list[str] = []

    # 1. Note 記事から生成
    if available_notes:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        note_url = ""
        m = re.search(r'NOTE_URL:\s*(https?://\S+)', note_text)
        if m:
            note_url = m.group(1)

        candidates = generate_posts_from_notes(note_text, feedback_text, note_url)
        if candidates:
            all_candidates = candidates
            tweet = select_best_tweet(candidates)
            source = f"Note: {note_file.stem}"
            log_key = note_file.name
            if note_url:
                image_bytes = fetch_article_image(note_url)

    # 2. RSS ニュースから生成（Note がない or 生成失敗時）
    if not tweet:
        candidates, article_link = generate_posts_from_rss()
        if candidates:
            all_candidates = candidates
            tweet = select_best_tweet(candidates)
            source = "AIニュース"
            log_key = "rss"
            if article_link:
                image_bytes = fetch_article_image(article_link)

    if not tweet:
        print("投稿候補が生成できませんでした。")
        sys.exit(1)

    tweet_id = ""

    # 3. X に自動投稿
    if x_api_available():
        try:
            tweet_id = post_to_x(tweet, image_bytes)
            append_to_log(log_key, f"x:{tweet_id}")

            # LINE に投稿確認通知
            if line_available():
                msg = build_posted_notification(tweet, tweet_id, source)
                send_line_notification(
                    os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
                    os.environ["LINE_USER_ID"],
                    msg,
                )
                print(f"[LINE確認通知送信] {source}")
            return

        except Exception as e:
            print(f"[X投稿失敗] {e}")
            # 失敗した場合は LINE に下書きとして通知

    # 4. X API 未設定 or 投稿失敗 → LINE に下書き通知
    if line_available():
        msg = build_draft_notification(all_candidates or [tweet], source)
        if send_line_notification(
            os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
            os.environ["LINE_USER_ID"],
            msg,
        ):
            append_to_log(log_key, "line_notified")
            print(f"[LINE通知完了] {source}")
            return

    print("X投稿もLINE通知も失敗しました。")
    sys.exit(1)


if __name__ == "__main__":
    main()
