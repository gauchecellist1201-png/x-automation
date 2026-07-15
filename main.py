"""
毎日21:00 JST にAI投稿案を生成してX自動投稿+LINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss

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
    return response.status_code == 200


def post_to_x(tweet_text: str) -> str | None:
    """X APIを使って直接投稿する。成功時はツイートID、失敗時はNoneを返す"""
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_SECRET"],
        )
        response = client.create_tweet(text=tweet_text)
        return str(response.data["id"])
    except ImportError:
        print("[X投稿] tweepyがインストールされていません")
        return None
    except Exception as e:
        print(f"[X投稿失敗] {e}")
        return None


def build_line_message(
    posts: list[str],
    source: str,
    posted_tweet: str = "",
    tweet_id: str = "",
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🤖 今日({today})のX投稿案 [{source}]", "─" * 20]

    if posted_tweet and tweet_id:
        lines.append(f"\n✅ X自動投稿済み:\n{posted_tweet}")
        lines.append(f"🔗 https://x.com/GAUCHE_cellist/status/{tweet_id}")
        lines.append("─" * 20)
        remaining = [p for p in posts if p != posted_tweet]
        if remaining:
            lines.append("\n📝 その他の候補:")
    else:
        remaining = posts
        lines.append("")

    for i, post in enumerate(remaining[:3], 1):
        lines.append(f"【案{i}】\n{post}")
        lines.append("─" * 20)

    if not posted_tweet:
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")

    return "\n".join(lines)


def parse_note_url(note_text: str) -> str:
    """Note本文からNOTE_URLを抽出する"""
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split("NOTE_URL:", 1)[1].strip()
    return ""


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    has_x_creds = all(
        os.environ.get(k)
        for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    )

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = "AIニュース"
    log_key = "rss"

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        note_url = parse_note_url(note_text)
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
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

    best_post = posts[0]
    tweet_id = ""

    # X自動投稿（クレデンシャルがある場合）
    if has_x_creds:
        tweet_id = post_to_x(best_post) or ""
        if tweet_id:
            append_to_log(f"{log_key}\t{date.today()}\t{tweet_id}")
            print(f"[X投稿完了] tweet_id={tweet_id}")
            print(f"{best_post}")

    # LINE通知
    if line_token and line_user_id:
        message = build_line_message(
            posts, source, best_post if tweet_id else "", tweet_id
        )
        if send_line_message(line_token, line_user_id, message):
            if not tweet_id:
                append_to_log(f"{log_key}\t{date.today()}\tline_notified")
            print(f"[LINE通知完了] {source}")
        else:
            print("[LINE通知失敗]")
            sys.exit(1)
        return

    if not has_x_creds:
        print("[警告] X/LINEのクレデンシャルが設定されていません。投稿案を表示します:")
        for i, p in enumerate(posts, 1):
            print(f"\n【案{i}】\n{p}\n{'─' * 40}")


if __name__ == "__main__":
    main()
