"""
毎日21:00 JST にAI投稿を生成・X自動投稿・LINE通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss, select_best_tweet

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> set[str]:
    if not LOG_FILE.exists():
        return set()
    posted: set[str] = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
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


def build_line_message(posts: list[str], best: str, source: str, tweet_url: str = "") -> str:
    today = date.today().strftime("%Y/%m/%d")
    others = [p for p in posts if p != best]

    lines = [
        f"\n🤖 今日({today})のX投稿 [{source}]",
        "─" * 20,
    ]

    if tweet_url:
        lines.append(f"\n✅ 自動投稿済み:\n{best}")
        lines.append(f"\n🔗 {tweet_url}")
    else:
        lines.append(f"\n✅ 推奨投稿案:\n{best}")

    if others:
        lines.append("\n─" * 20)
        lines.append("\n📋 他の候補案:")
        for i, post in enumerate(others, 1):
            lines.append(f"\n【案{i}】\n{post}")

    lines.append("\n" + "─" * 20)
    if not tweet_url:
        lines.append("\n👆 気に入った案をコピーしてXに投稿してください！")

    return "\n".join(lines)


def post_to_x(text: str) -> str | None:
    """X(Twitter) API v2 で投稿。APIキーがない場合はNoneを返す。"""
    try:
        import tweepy
    except ImportError:
        print("[X投稿スキップ] tweepyがインストールされていません")
        return None

    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_secret = os.environ.get("X_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("[X投稿スキップ] APIキーが設定されていません")
        return None

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    try:
        response = client.create_tweet(text=text)
        if response.data:
            tweet_id = str(response.data["id"])
            print(f"[X投稿完了] ID: {tweet_id}")
            return tweet_id
    except Exception as e:
        print(f"[X投稿エラー] {e}")
    return None


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = "AIニュース"
    log_key = "rss"

    # Note記事から生成（未投稿のものがあれば優先）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            source = f"Note: {note_file.stem}"
            log_key = note_file.name

    # RSSニュースから生成（フォールバック）
    if not posts:
        posts = generate_posts_from_rss()
        log_key = "rss"

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # 最良の投稿をClaudeが選択
    best = select_best_tweet(posts)

    # X自動投稿
    tweet_id = post_to_x(best)
    tweet_url = f"https://x.com/GAUCHE_cellist/status/{tweet_id}" if tweet_id else ""

    # LINE通知
    if line_token and line_user_id:
        message = build_line_message(posts, best, source, tweet_url)
        if send_line_message(line_token, line_user_id, message):
            print("[LINE通知完了]")

    # ログ更新
    status = tweet_id if tweet_id else "line_notified"
    append_to_log(f"{log_key}\t{date.today()}\t{status}")
    print(f"[完了] source={source} | tweet={best[:50]}...")


if __name__ == "__main__":
    main()
