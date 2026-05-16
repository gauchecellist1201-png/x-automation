"""
毎日21:00 JST にAI関連ツイートを自動生成・X投稿し、LINEに通知するスクリプト
- X API が設定済みなら自動投稿 → LINE に投稿結果を通知
- X API 未設定なら投稿案を LINE に送信して手動投稿を促す
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date

from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_news,
    fetch_top_news,
    NewsItem,
    MAX_TWEET_CHARS,
    URL_WEIGHT,
)
from tweet_poster import post_tweet, x_api_available

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
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=15)
        return response.status_code == 200
    except Exception:
        return False


def attach_url(tweet: str, url: str) -> str:
    """ツイート本文にURLを付加（140文字制限を考慮）"""
    if not url:
        return tweet
    text_len = len(tweet.replace('\n', ''))
    # URL付加後が制限内に収まる場合のみ付加（URL=23文字換算）
    if text_len + URL_WEIGHT + 1 <= MAX_TWEET_CHARS * 2:  # CJK混在を考慮して余裕を持たせる
        return f"{tweet}\n{url}"
    return tweet


def select_best_tweet(posts: list[str]) -> str:
    """リストの先頭（スコア最高）を返す（スコアリングはcontent_gen側で実施済み）"""
    return posts[0] if posts else ""


def build_line_message(
    posts: list[str],
    source: str,
    posted_result: dict | None,
    selected_news: NewsItem | None,
    best_tweet_text: str,
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🤖 今日({today})のAI投稿 [{source}]", "─" * 22]

    if posted_result and posted_result.get("success"):
        lines += [
            "\n✅ X自動投稿完了！",
            f"🔗 {posted_result['url']}",
            f"\n📝 投稿内容:\n{best_tweet_text}",
            "─" * 22,
        ]
        remaining = posts[1:3]
        if remaining:
            lines.append("\n📋 他の候補案（参考）:")
            for i, p in enumerate(remaining, 2):
                lines += [f"\n【案{i}】\n{p}", "─" * 22]
    else:
        if posted_result:
            lines += [f"\n⚠️ X投稿失敗: {posted_result.get('error', '不明')}", "─" * 22]
        for i, p in enumerate(posts[:3], 1):
            lines += [f"\n【案{i}】\n{p}", "─" * 22]
        lines.append("\n📋 気に入った案をコピーしてXに投稿してください！")

    if selected_news and selected_news.url:
        lines.append(f"\n📰 参考記事: {selected_news.url}")
    if selected_news and selected_news.image_url:
        lines.append(f"🖼 画像: {selected_news.image_url}")

    return "\n".join(lines)


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    has_line = bool(line_token and line_user_id)
    has_x = x_api_available()

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = ""
    selected_news: NewsItem | None = None
    posted_result: dict | None = None
    best_tweet = ""

    # ── Note記事から生成 ────────────────────────────────────────────
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # NOTE_URL を抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split(":", 1)[1].strip()
                break

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        source = f"Note: {note_file.stem}"

        if posts:
            best = select_best_tweet(posts)
            best_tweet = attach_url(best, note_url) if note_url else best

            if has_x:
                posted_result = post_tweet(best_tweet)
                log_suffix = (
                    f"x_posted\t{posted_result['url']}"
                    if posted_result.get("success")
                    else "x_failed"
                )
            else:
                log_suffix = "line_notified"

            append_to_log(f"{note_file.name}\t{date.today()}\t{log_suffix}")

    # ── RSSニュースから生成（Noteがない or 生成失敗時） ───────────────
    if not posts:
        news_items = fetch_top_news()
        posts, selected_news = generate_posts_from_news(news_items)
        source = "AIニュース"

        if posts:
            best = select_best_tweet(posts)
            best_tweet = attach_url(best, selected_news.url if selected_news else "")

            if has_x:
                posted_result = post_tweet(best_tweet)
                log_suffix = (
                    f"x_posted\t{posted_result['url']}"
                    if posted_result.get("success")
                    else "x_failed"
                )
            else:
                log_suffix = "line_notified"

            append_to_log(f"rss\t{date.today()}\t{log_suffix}")

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # ── LINE通知 ──────────────────────────────────────────────────
    if has_line:
        message = build_line_message(posts, source, posted_result, selected_news, best_tweet)
        ok = send_line_message(line_token, line_user_id, message)
        print(f"[LINE{'通知完了' if ok else '通知失敗'}] {source}")

    # ── ターミナル出力（GitHub Actions ログ用） ─────────────────────
    if posted_result and posted_result.get("success"):
        print(f"[X投稿完了] {posted_result['url']}")
        print(f"[投稿内容] {best_tweet[:80]}...")
    elif posts:
        print(f"[生成完了] {source}: {posts[0][:60]}...")


if __name__ == "__main__":
    main()
