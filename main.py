"""
毎日21:00 JST にAI投稿を自動生成 → X自動投稿 → LINE通知するスクリプト
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
    select_best_tweet,
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


def post_to_x(tweet: str) -> str | None:
    """X APIでツイートを投稿してツイートIDを返す。認証情報がなければNoneを返す"""
    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_secret = os.environ.get("X_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        return None

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    response = client.create_tweet(text=tweet)
    return str(response.data["id"])


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


def build_posted_line_message(posted_tweet: str, tweet_id: str | None, other_candidates: list[str]) -> str:
    """X投稿済みの場合のLINEメッセージ"""
    today = date.today().strftime("%Y/%m/%d")
    tweet_url = f"https://x.com/GAUCHE_cellist/status/{tweet_id}" if tweet_id else "（投稿済み）"
    lines = [
        f"✅ {today} の投稿が完了しました！",
        "─" * 20,
        f"【投稿内容】\n{posted_tweet}",
        f"\n🔗 {tweet_url}",
    ]
    if other_candidates:
        lines.append("\n─" * 20)
        lines.append("【他の候補案（手動投稿用）】")
        for i, c in enumerate(other_candidates, 1):
            lines.append(f"\n案{i}: {c}")
    return "\n".join(lines)


def build_notify_line_message(posts: list[str], source: str) -> str:
    """X API未設定時の手動投稿用LINEメッセージ"""
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = ""

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        candidates = generate_posts_from_notes(note_text, feedback_text)
        if candidates:
            posts = candidates
            source = f"Note: {note_file.stem}"
            log_key = note_file.name

    # RSSニュースから生成（Noteがない or 生成失敗時）
    if not posts:
        candidates = generate_posts_from_rss()
        if candidates:
            posts = candidates
            source = "AIニュース"
            log_key = "rss"

    if not posts:
        print("投稿候補が生成できませんでした。")
        sys.exit(0)

    # 最もバズりそうな1案を選択
    best = select_best_tweet(posts)
    others = [p for p in posts if p != best]

    # X APIで自動投稿を試みる
    tweet_id = post_to_x(best)

    if tweet_id:
        # 自動投稿成功 → LINEに「投稿済み通知」
        message = build_posted_line_message(best, tweet_id, others)
        send_line_message(line_token, line_user_id, message)
        append_to_log(f"{log_key}\t{date.today()}\t{tweet_id}")
        print(f"[X投稿完了] tweet_id={tweet_id}\n{best}")
    else:
        # X API未設定 → LINEに「手動投稿用候補」を送信
        message = build_notify_line_message(posts, source)
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"{log_key}\t{date.today()}\tline_notified")
            print(f"[LINE通知完了] {source}")
        else:
            print("[エラー] LINE通知に失敗しました。")
            sys.exit(1)


if __name__ == "__main__":
    main()
