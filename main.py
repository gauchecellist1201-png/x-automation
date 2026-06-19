"""
毎日 JST 21:00 に実行:
1. AIトレンドを分析してビジネス層向けバイラル投稿を生成
2. X/Twitter に自動投稿（認証情報が設定されている場合）
3. 投稿結果（または候補案）を LINE に通知
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
    generate_viral_posts,
    select_best_post,
)
from trend_analyzer import get_trend_context
from x_poster import is_x_configured, post_tweet, build_tweet_url

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")
X_USERNAME = os.environ.get("X_USERNAME", "GAUCHE_cellist")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> set[str]:
    if not LOG_FILE.exists():
        return set()
    lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    return {line.split("\t")[0] for line in lines if line.strip()}


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


def build_success_line_message(tweet_text: str, tweet_id: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    tweet_url = build_tweet_url(tweet_id, X_USERNAME)
    return (
        f"\n✅ 今日({today})のX投稿が完了しました！ [{source}]\n"
        f"{'─' * 20}\n"
        f"{tweet_text}\n"
        f"{'─' * 20}\n"
        f"🔗 {tweet_url}"
    )


def build_candidates_line_message(posts: list[str], source: str, top_url: str = "") -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)
    if top_url:
        lines.append(f"\n📰 参考記事: {top_url}")
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def build_final_tweet(post_text: str, article_url: str = "") -> str:
    """投稿本文にURLを付加して最終ツイートを組み立てる。"""
    if article_url:
        return f"{post_text}\n{article_url}"
    return post_text


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    use_line = bool(line_token and line_user_id)
    use_x = is_x_configured()

    if not use_line and not use_x:
        print("ERROR: LINE または X の認証情報が設定されていません。")
        sys.exit(1)

    # ─── トレンド分析 ───────────────────────────────────────────
    print("[1/4] AIトレンドを分析中...")
    try:
        trend_context = get_trend_context()
    except Exception as e:
        print(f"トレンド分析エラー（フォールバック）: {e}")
        trend_context = {"news": [], "top_news": None, "buzz_analysis": ""}

    top_news = trend_context.get("top_news")
    top_url = top_news["url"] if top_news else ""

    # ─── 投稿案の生成 ───────────────────────────────────────────
    print("[2/4] 投稿案を生成中...")
    posted = load_posted_log()
    unposted = get_unposted_notes(posted)
    source = "AIニュース"
    posts: list[str] = []

    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            source = f"Note: {note_file.stem}"
            top_url = ""  # Note 由来なのでニュースURLは使わない

    if not posts:
        posts = generate_viral_posts(trend_context) if trend_context["news"] else []

    if not posts:
        posts = generate_posts_from_rss()

    if not posts:
        print("投稿候補が生成できませんでした。")
        sys.exit(1)

    # ─── X/Twitter 自動投稿 ─────────────────────────────────────
    tweet_id: str | None = None
    best_post: str | None = None

    if use_x:
        print("[3/4] X に投稿中...")
        best_post = select_best_post(posts)
        if best_post:
            final_tweet = build_final_tweet(best_post, top_url)
            tweet_id = post_tweet(final_tweet)

    # ─── LINE 通知 ───────────────────────────────────────────────
    if use_line:
        print("[4/4] LINE に通知中...")
        if tweet_id and best_post:
            final_tweet_text = build_final_tweet(best_post, top_url)
            message = build_success_line_message(final_tweet_text, tweet_id, source)
        else:
            message = build_candidates_line_message(posts, source, top_url)
        send_line_message(line_token, line_user_id, message)

    # ─── ログ記録 ────────────────────────────────────────────────
    today = date.today()
    if tweet_id:
        status = f"x_posted:{tweet_id}"
        log_key = top_news["title"][:50] if (top_news and source == "AIニュース") else source
        append_to_log(f"{log_key}\t{today}\t{status}")
        print(f"[完了] X投稿成功 tweet_id={tweet_id}")
    elif unposted and source.startswith("Note:"):
        append_to_log(f"{unposted[0].name}\t{today}\tline_notified")
        print(f"[完了] LINE通知のみ Note: {source}")
    else:
        append_to_log(f"rss\t{today}\tline_notified")
        print("[完了] LINE通知のみ RSSニュース")


if __name__ == "__main__":
    main()
