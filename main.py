"""
毎日21:00 JST にAI投稿を自動生成してXに投稿し、LINEにも通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss, _generate_original_ai_insight
from x_poster import post_tweet, build_tweet_url

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
    try:
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[LINE通知失敗] {e}")
        return False


def build_line_message(tweet_text: str, tweet_url: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿 [{source}]",
        "─" * 20,
        tweet_text,
        "─" * 20,
    ]
    if tweet_url:
        lines.append(f"🔗 {tweet_url}")
    return "\n".join(lines)


def _try_post(posts: list[str], source: str, article_url: str) -> bool:
    """投稿候補から最初の有効なものをXに投稿し、LINEに通知。成功したらTrueを返す。"""
    if not posts:
        return False

    tweet_text = posts[0]
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    tweet_id = post_tweet(tweet_text)
    if tweet_id:
        tweet_url = build_tweet_url(tweet_id)
        append_to_log(f"{source}\t{date.today()}\t{tweet_id}")
        print(f"[投稿完了] {tweet_url}")

        if line_token and line_user_id:
            msg = build_line_message(tweet_text, tweet_url, source)
            send_line_message(line_token, line_user_id, msg)
        return True

    # X投稿失敗時はLINEに候補を通知（手動投稿用）
    if line_token and line_user_id:
        today = date.today().strftime("%Y/%m/%d")
        lines = [f"\n⚠️ X自動投稿失敗({today}) [{source}]", "─" * 20]
        for i, p in enumerate(posts[:3], 1):
            lines.append(f"\n【案{i}】\n{p}")
            lines.append("─" * 20)
        if article_url:
            lines.append(f"\n📰 元記事: {article_url}")
        lines.append("\n✅ 手動でXに投稿してください")
        send_line_message(line_token, line_user_id, "\n".join(lines))
    return False


def main() -> None:
    posted = load_posted_log()
    unposted = get_unposted_notes(posted)
    feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

    # Note記事から生成（未投稿のものがある場合）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        posts = generate_posts_from_notes(note_text, feedback_text)
        if _try_post(posts, f"note:{note_file.stem}", ""):
            return

    # RSSニュースから生成
    posts, article_url = generate_posts_from_rss()
    if _try_post(posts, "rss", article_url):
        return

    # オリジナル洞察から生成（フォールバック）
    posts, _ = _generate_original_ai_insight()
    if _try_post(posts, "original", ""):
        return

    print("投稿候補がありませんでした。")
    sys.exit(1)


if __name__ == "__main__":
    main()
