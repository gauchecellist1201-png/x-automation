"""
毎日21:00 JST にAI投稿を生成・自動投稿するスクリプト
X APIキーがある場合: 自動投稿 → LINE通知（投稿内容を共有）
X APIキーがない場合: LINE通知のみ（下書き3案を送信）
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
    fetch_rss_news,
)
from viral_analyzer import get_viral_ai_tweets
from x_poster import post_tweet, upload_image_from_url

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


def has_x_credentials() -> bool:
    return all(
        os.environ.get(k)
        for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    )


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
        r = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def build_line_posted(post: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    return (
        f"\n✅ 今日({today})のX投稿完了！ [{source}]\n"
        + "─" * 22
        + f"\n{post}\n"
        + "─" * 22
        + "\n📊 エンゲージメントを確認してください"
    )


def build_line_drafts(posts: list[str], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 22,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 22)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def fetch_ogp_image_url(article_url: str) -> str | None:
    """ニュース記事からOGP画像URLを取得（regex使用、依存ライブラリなし）"""
    if not article_url:
        return None
    try:
        r = requests.get(
            article_url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (compatible; bot/1.0)"},
        )
        if r.status_code != 200:
            return None
        content = r.text
        # og:image メタタグを2パターンで検索
        patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        ]
        for pat in patterns:
            m = re.search(pat, content, re.IGNORECASE)
            if m:
                img_url = m.group(1).strip()
                if img_url.startswith("http"):
                    return img_url
    except Exception:
        pass
    return None


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    auto_post = has_x_credentials()

    # 1. バズパターン取得（X Bearer Token がある場合のみ）
    print("バズパターンを取得中...")
    viral_tweets = get_viral_ai_tweets()
    print(f"バズツイート {len(viral_tweets)} 件取得")

    # 2. 最新ニュース取得（RSS共有してOGP画像にも再利用）
    news_items = fetch_rss_news()

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = ""
    log_key = "rss"
    top_article_url = news_items[0]["url"] if news_items else ""

    # 3. Note記事 or RSSから投稿案を生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(
            note_text,
            feedback_text,
            viral_tweets=viral_tweets,
        )
        source = f"Note: {note_file.stem}"
        log_key = note_file.name

    if not posts:
        posts = generate_posts_from_rss(viral_tweets=viral_tweets, news_items=news_items)
        source = "AIニュース"
        log_key = "rss"

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # 4. X自動投稿モード
    if auto_post:
        best_post = posts[0]

        # OGP画像を取得してアップロード（失敗しても投稿は継続）
        media_id: str | None = None
        if top_article_url:
            print(f"OGP画像を取得中: {top_article_url}")
            ogp_url = fetch_ogp_image_url(top_article_url)
            if ogp_url:
                print(f"OGP画像URL: {ogp_url}")
                media_id = upload_image_from_url(ogp_url)
                print(f"メディアID: {media_id}")

        result = post_tweet(best_post, media_ids=[media_id] if media_id else None)

        if result["ok"]:
            append_to_log(f"{log_key}\t{date.today()}\tx_posted")
            print(f"[X投稿完了] {source}")
            if line_token and line_user_id:
                msg = build_line_posted(best_post, source)
                send_line_message(line_token, line_user_id, msg)
            return
        else:
            print(f"[X投稿失敗] status={result['status_code']} body={result['data']} → LINE通知に切替")

    # 5. LINE通知（下書き送付）
    if line_token and line_user_id:
        msg = build_line_drafts(posts, source)
        if send_line_message(line_token, line_user_id, msg):
            append_to_log(f"{log_key}\t{date.today()}\tline_notified")
            print(f"[LINE通知完了] {source}")
            return

    print("通知も失敗しました。")
    sys.exit(1)


if __name__ == "__main__":
    main()
