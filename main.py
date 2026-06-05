"""
毎日AIニュースをビジネス層に届けるX自動投稿スクリプト

朝 07:30 JST: 最新AIニュース + リンク付き投稿（通勤時間帯）
夜 21:00 JST: 深い洞察スレッド（エンゲージメント最大化）
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date, datetime, timezone, timedelta

from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    generate_evening_thread,
    fetch_rss_items,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
JST = timezone(timedelta(hours=9))


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
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    resp = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    return resp.status_code == 200


def build_line_message(posts: list[str], source: str, tweet_id: str | None = None) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🤖 今日({today})のX投稿案 [{source}]", "─" * 20]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)
    if tweet_id:
        lines.append(f"\n✅ X自動投稿完了！")
        lines.append(f"🔗 https://x.com/i/web/status/{tweet_id}")
    else:
        lines.append("\n📋 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def x_api_enabled() -> bool:
    return all(
        k in os.environ
        for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    )


def auto_post_to_x(post: str, image_url: str | None = None) -> str | None:
    """Xに自動投稿し、成功したらtweet_idを返す"""
    from x_poster import post_tweet, upload_media_from_url

    media_id = None
    if image_url:
        media_id = upload_media_from_url(image_url)

    result = post_tweet(post, media_id)
    return result["id"] if result else None


def main() -> None:
    now_jst = datetime.now(JST)
    is_morning = now_jst.hour < 12  # 朝7:30 vs 夜21:00
    run_type = "morning" if is_morning else "evening"

    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")
    posted = load_posted_log()

    posts: list[str] = []
    source_label = ""
    image_url: str | None = None
    is_thread = False
    thread_tweets: list[str] = []

    if is_morning:
        # 朝: 最新AIニュース + リンク付き投稿
        print("[朝投稿] 最新AIニュース取得中...")
        posts, best_article = generate_posts_from_rss()
        source_label = "AIニュース（朝）"
        if best_article:
            image_url = best_article.get("image_url")
            print(f"[選択記事] {best_article.get('title', 'N/A')}")
    else:
        # 夜: Note記事から投稿 → なければ洞察スレッド
        print("[夜投稿] コンテンツ生成中...")
        unposted = get_unposted_notes(posted)
        if unposted:
            note_file = random.choice(unposted)
            note_text = note_file.read_text(encoding="utf-8")
            feedback_text = (
                FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
            )
            posts = generate_posts_from_notes(note_text, feedback_text)
            source_label = f"Note: {note_file.stem}"
            if posts:
                append_to_log(f"{note_file.name}\t{date.today()}\t{run_type}")

        if not posts:
            # 洞察スレッド生成
            rss_items = fetch_rss_items(max_items=5)
            thread_tweets = generate_evening_thread(rss_items if rss_items else None)
            if thread_tweets:
                is_thread = True
                source_label = "洞察スレッド（夜）"
                posts = thread_tweets

    if not posts:
        print("投稿候補が生成できませんでした。")
        sys.exit(0)

    # X自動投稿
    tweet_id: str | None = None
    if x_api_enabled():
        if is_thread and thread_tweets:
            from x_poster import post_thread
            tweet_id = post_thread(thread_tweets)
            if tweet_id:
                append_to_log(f"thread\t{date.today()}\t{run_type}\t{tweet_id}")
        elif posts:
            tweet_id = auto_post_to_x(posts[0], image_url)
            if tweet_id:
                append_to_log(f"x_posted\t{date.today()}\t{run_type}\t{tweet_id}")
    else:
        print("[X APIキー未設定] LINE通知のみ")

    # LINE通知
    if line_token and line_user_id:
        message = build_line_message(posts, source_label, tweet_id)
        if send_line_message(line_token, line_user_id, message):
            if not tweet_id:
                append_to_log(f"line_only\t{date.today()}\t{run_type}")
            print(f"[LINE通知完了] {source_label}")
    elif not tweet_id:
        print("生成された投稿:")
        for i, p in enumerate(posts[:3], 1):
            print(f"  [{i}] {p}")


if __name__ == "__main__":
    main()
