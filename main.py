"""
毎日JST 21:00 にAI関連の投稿を生成し、X（旧Twitter）に自動投稿 + LINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from typing import Optional

from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    generate_thread,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
TWITTER_API_URL = "https://api.twitter.com/2/tweets"


# ─── ログ管理 ────────────────────────────────────────────────────────────────

def load_posted_log() -> set[str]:
    """投稿済みファイル名のセットを返す（タブ区切り形式を正しく解析）"""
    if not LOG_FILE.exists():
        return set()
    posted = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if parts:
            posted.add(parts[0])  # ファイル名のみ抽出
    return posted


def append_to_log(filename: str, tweet_id: str = "line_notified") -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{filename}\t{date.today()}\t{tweet_id}\n")


def get_unposted_notes(posted: set[str]) -> list[Path]:
    """まだ投稿していないNoteファイルを返す"""
    if not NOTES_DIR.exists():
        return []
    return [p for p in sorted(NOTES_DIR.glob("*.md")) if p.name not in posted]


# ─── LINE通知 ─────────────────────────────────────────────────────────────────

def send_line_message(token: str, user_id: str, message: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
    if response.status_code != 200:
        print(f"[LINE ERROR] {response.status_code}: {response.text}")
    return response.status_code == 200


def build_line_message(posts: list[str], source: str, posted_url: str = "") -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 22,
    ]
    for i, post in enumerate(posts[:3], 1):
        char_count = len(post)
        lines.append(f"\n【案{i}】({char_count}文字)\n{post}")
        lines.append("─" * 22)

    if posted_url:
        lines.append(f"\n📰 参考ニュース:\n{posted_url}")
        lines.append("─" * 22)

    lines.append("\n✅ X投稿を確認・修正してから投稿してください！")
    return "\n".join(lines)


# ─── X API 自動投稿 ──────────────────────────────────────────────────────────

def post_to_x(tweet_text: str) -> Optional[str]:
    """X APIに投稿する。成功時はツイートIDを返す。認証情報がなければNoneを返す。"""
    try:
        import tweepy
    except ImportError:
        print("[X投稿] tweepyがインストールされていません。スキップします。")
        return None

    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_KEY_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        print("[X投稿] Twitter API認証情報が未設定のため、自動投稿をスキップします。")
        return None

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    response = client.create_tweet(text=tweet_text)
    tweet_id = str(response.data["id"])
    tweet_url = f"https://x.com/GAUCHE_cellist/status/{tweet_id}"
    print(f"[X投稿完了] {tweet_url}")
    return tweet_id


def post_thread_to_x(tweets: list[str]) -> Optional[str]:
    """スレッド（連続ツイート）をX APIに投稿する。最初のツイートIDを返す。"""
    try:
        import tweepy
    except ImportError:
        return None

    api_key = os.environ.get("TWITTER_API_KEY")
    api_secret = os.environ.get("TWITTER_API_KEY_SECRET")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        return None

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )

    first_id = None
    reply_to_id = None

    for i, tweet_text in enumerate(tweets):
        kwargs = {"text": tweet_text}
        if reply_to_id:
            kwargs["in_reply_to_tweet_id"] = reply_to_id
        response = client.create_tweet(**kwargs)
        tweet_id = str(response.data["id"])
        if i == 0:
            first_id = tweet_id
        reply_to_id = tweet_id
        print(f"[スレッド {i+1}/{len(tweets)}] ツイートID: {tweet_id}")

    return first_id


# ─── メイン処理 ───────────────────────────────────────────────────────────────

def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    has_line = bool(line_token and line_user_id)

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    tweet_id: Optional[str] = None
    source_label = ""
    best_post = ""
    posted_url = ""

    # ① Note記事から投稿生成（未投稿のものを優先）
    if unposted:
        note_file = unposted[0]  # ランダムではなく順番に消化
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # NOTE_URLをファイル内から抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.replace("NOTE_URL:", "").strip()
                break

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            source_label = f"Note: {note_file.stem}"
            best_post = posts[0]

            # X自動投稿
            tweet_id = post_to_x(best_post)

            # LINE通知（全候補を送信）
            if has_line:
                message = build_line_message(posts, source_label, note_url)
                send_line_message(line_token, line_user_id, message)

            log_id = tweet_id or "line_notified"
            append_to_log(note_file.name, log_id)
            print(f"[完了] Note: {note_file.name} → {log_id}")
            return

    # ② RSSニュースから投稿生成
    posts, posted_url = generate_posts_from_rss()
    if posts:
        source_label = "AIニュース"
        best_post = posts[0]

        # X自動投稿（最も良い案を投稿）
        tweet_id = post_to_x(best_post)

        # LINE通知（全候補を送信）
        if has_line:
            message = build_line_message(posts, source_label, posted_url)
            send_line_message(line_token, line_user_id, message)

        log_id = tweet_id or "line_notified"
        append_to_log("rss", log_id)
        print(f"[完了] RSSニュース → {log_id}")

        # スレッド候補も生成して LINE通知
        if has_line and len(posts) >= 1:
            thread_tweets = generate_thread(best_post, posted_url)
            if thread_tweets:
                thread_message = (
                    f"\n🧵 スレッド投稿案（エンゲージメント向上用）\n"
                    f"{'─' * 22}\n"
                    + "\n---\n".join(f"[{i+1}]:\n{t}" for i, t in enumerate(thread_tweets))
                )
                send_line_message(line_token, line_user_id, thread_message)

        return

    print("[警告] 投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
