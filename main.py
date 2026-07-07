"""
毎日 21:00 JST に最新 AI ニュースからバズる投稿を生成し、
X（Twitter）に自動投稿 + LINE に通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date, timedelta

import tweepy

from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    select_best_tweet,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
NOTE_REUSE_DAYS = 14  # 同じ Note を再利用するまでの日数


# ── ログ管理 ────────────────────────────────────────────────

def load_log_lines() -> list[str]:
    if not LOG_FILE.exists():
        return []
    return LOG_FILE.read_text(encoding="utf-8").splitlines()


def get_recently_used_notes(log_lines: list[str], days: int = NOTE_REUSE_DAYS) -> set[str]:
    """過去 N 日以内に使用した Note ファイル名のセットを返す"""
    cutoff = date.today() - timedelta(days=days)
    recent: set[str] = set()
    for line in log_lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        source = parts[0]
        if not source.endswith(".md"):
            continue
        try:
            used_date = date.fromisoformat(parts[1])
            if used_date >= cutoff:
                recent.add(source)
        except ValueError:
            pass
    return recent


def append_to_log(source: str, tweet_id: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{source}\t{date.today()}\t{tweet_id}\n")


# ── Note ファイル取得 ────────────────────────────────────────

def get_available_notes(recently_used: set[str]) -> list[Path]:
    if not NOTES_DIR.exists():
        return []
    return [p for p in NOTES_DIR.glob("*.md") if p.name not in recently_used]


def extract_note_url(note_text: str) -> str:
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split(":", 1)[1].strip()
    return ""


# ── X（Twitter）投稿 ────────────────────────────────────────

def post_to_x(text: str) -> str | None:
    """X API v2 で投稿し tweet_id を返す。認証情報が未設定なら None を返す。"""
    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_secret = os.environ.get("X_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("[X投稿スキップ] X API キーが未設定です")
        return None

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    response = client.create_tweet(text=text)
    return str(response.data["id"])


# ── LINE 通知 ────────────────────────────────────────────────

def send_line_message(token: str, user_id: str, message: str) -> bool:
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


def build_line_message(post: str, source: str, tweet_id: str | None) -> str:
    today = date.today().strftime("%Y/%m/%d")
    if tweet_id:
        status_line = f"✅ X 投稿完了\n🔗 https://x.com/GAUCHE_cellist/status/{tweet_id}"
    else:
        status_line = "⚠️ X 投稿はスキップ（API キー未設定）"
    return (
        f"\n🤖 【{today} AI 自動投稿】\n"
        f"{'─' * 22}\n"
        f"ソース: {source}\n\n"
        f"📝 投稿内容:\n{post}\n\n"
        f"{'─' * 22}\n"
        f"{status_line}"
    )


# ── メイン ───────────────────────────────────────────────────

def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    log_lines = load_log_lines()
    recently_used = get_recently_used_notes(log_lines)
    available_notes = get_available_notes(recently_used)

    best_post: str = ""
    source_label: str = ""

    # 1) Note 記事から生成
    if available_notes:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_url = extract_note_url(note_text)

        candidates = generate_posts_from_notes(note_text, feedback_text, note_url)
        if candidates:
            best_post = select_best_tweet(candidates)
            source_label = note_file.name

    # 2) RSS ニュースから生成（Note なし or 生成失敗）
    if not best_post:
        candidates, _ = generate_posts_from_rss()
        if candidates:
            best_post = select_best_tweet(candidates)
            source_label = "rss"

    if not best_post:
        print("投稿候補の生成に失敗しました。")
        sys.exit(1)

    # X 投稿
    tweet_id = post_to_x(best_post)

    # LINE 通知
    if line_token and line_user_id:
        message = build_line_message(best_post, source_label, tweet_id)
        send_line_message(line_token, line_user_id, message)

    # ログ記録
    append_to_log(source_label, tweet_id or "line_only")
    print(f"[完了] source={source_label} tweet_id={tweet_id}")


if __name__ == "__main__":
    main()
