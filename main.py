"""
毎日21:00 JST にAI投稿を生成してXに自動投稿するスクリプト
LINE通知で投稿内容を確認できる（オプション）
"""

import os
import sys
import random
import requests
import tweepy
from pathlib import Path
from datetime import date
from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    pick_best_tweet,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


# ─── ログ管理 ────────────────────────────────────────────────

def load_posted_filenames() -> set[str]:
    """投稿済みノートファイル名のセットを返す（タブ区切り行の先頭列だけ抽出）"""
    if not LOG_FILE.exists():
        return set()
    posted = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            parts = line.split("\t")
            if parts:
                posted.add(parts[0])
    return posted


def append_to_log(source: str, result: str) -> None:
    entry = f"{source}\t{date.today()}\t{result}"
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


# ─── コンテンツ選択 ──────────────────────────────────────────

def get_unposted_notes(posted: set[str]) -> list[Path]:
    if not NOTES_DIR.exists():
        return []
    return [p for p in NOTES_DIR.glob("*.md") if p.name not in posted]


# ─── X (Twitter) 投稿 ────────────────────────────────────────

def post_to_x(text: str) -> str | None:
    """X API v2 で投稿してツイートIDを返す。失敗時は None。"""
    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_secret = os.environ.get("X_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("[X投稿スキップ] X API認証情報が未設定")
        return None

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    response = client.create_tweet(text=text)
    if response.data:
        return str(response.data["id"])
    return None


# ─── LINE 通知 ───────────────────────────────────────────────

def send_line_notification(token: str, user_id: str, message: str) -> bool:
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


def build_line_result_message(tweet_text: str, tweet_id: str | None, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    status = f"✅ X投稿完了 (ID: {tweet_id})" if tweet_id else "⚠️ X投稿失敗（LINE確認用）"
    return (
        f"\n🤖 {today} の投稿 [{source}]\n"
        "─" * 20 + "\n"
        f"{tweet_text}\n"
        "─" * 20 + "\n"
        f"{status}"
    )


# ─── メイン ──────────────────────────────────────────────────

def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")

    posted = load_posted_filenames()
    unposted = get_unposted_notes(posted)
    feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

    tweet_text = ""
    source = ""

    # ── ① Noteファイルから生成 ───────────────────────────────
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")

        # NoteのURLをプロフィールから抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.replace("NOTE_URL:", "").strip()
                break

        candidates = generate_posts_from_notes(note_text, feedback_text, note_url)
        if candidates:
            tweet_text = pick_best_tweet(candidates)
            source = f"Note: {note_file.stem}"

    # ── ② RSSニュースから生成 ────────────────────────────────
    if not tweet_text:
        candidates, article_url = generate_posts_from_rss()
        if candidates:
            tweet_text = pick_best_tweet(candidates)
            source = "AIニュース"

    if not tweet_text:
        print("投稿候補を生成できませんでした。")
        sys.exit(1)

    print(f"[生成完了] {source}\n{tweet_text}")

    # ── X に投稿 ─────────────────────────────────────────────
    tweet_id = post_to_x(tweet_text)
    if tweet_id:
        print(f"[X投稿完了] https://x.com/GAUCHE_cellist/status/{tweet_id}")
        log_result = f"tweet_id:{tweet_id}"
    else:
        log_result = "x_post_failed"

    # ── ログ記録 ─────────────────────────────────────────────
    log_source = note_file.name if unposted and tweet_text else "rss"
    append_to_log(log_source, log_result)

    # ── LINE 通知（設定されている場合のみ） ──────────────────
    if line_token and line_user_id:
        message = build_line_result_message(tweet_text, tweet_id, source)
        if send_line_notification(line_token, line_user_id, message):
            print("[LINE通知完了]")
        else:
            print("[LINE通知失敗]")


if __name__ == "__main__":
    main()
