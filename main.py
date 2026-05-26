"""
毎日21:00 JST にAI投稿を自動生成してXに投稿するスクリプト
X APIキーがない場合はLINE通知にフォールバック
"""

import os
import re
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss
from x_poster import post_tweet

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> set[str]:
    """ログから投稿済みのファイル名セットを返す"""
    if not LOG_FILE.exists():
        return set()
    posted = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            posted.add(line.split("\t")[0])
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
    payload = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    try:
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[LINE送信エラー] {e}")
        return False


def build_line_message(
    posts: list[str], source: str, news_url: str = "", tweet_id: str = ""
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🤖 今日({today})のAI投稿 [{source}]", "─" * 22]

    if tweet_id:
        lines.insert(1, f"✅ X自動投稿済み:\nhttps://x.com/GAUCHE_cellist/status/{tweet_id}")

    for i, post in enumerate(posts[:3], 1):
        display = post
        if news_url and i == 1:
            display = f"{post}\n\n🔗 {news_url}"
        lines.append(f"\n【案{i}】\n{display}")
        lines.append("─" * 22)

    if not tweet_id:
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")

    return "\n".join(lines)


def compose_final_tweet(body: str, news_url: str = "") -> str:
    """本文＋URLを結合（280文字制限: URLは23文字換算）"""
    if not news_url:
        return body
    max_body = 280 - 24  # URL(23) + 改行(1)
    if len(body) > max_body:
        body = body[: max_body - 1] + "…"
    return f"{body}\n\n{news_url}"


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    has_x = all(
        os.environ.get(k)
        for k in ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    )

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    news_url: str = ""
    source: str = ""
    note_filename: str = ""

    # Note記事から生成（未投稿のものがある場合）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_url_match = re.search(r"NOTE_URL:\s*(https?://\S+)", note_text)
        note_url = note_url_match.group(1) if note_url_match else ""
        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            news_url = note_url
            source = f"Note: {note_file.stem}"
            note_filename = note_file.name

    # Note生成が失敗またはノートなし → RSSから生成
    if not posts:
        posts, news_url = generate_posts_from_rss()
        source = "AIニュース"

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    tweet_id: str = ""

    # X自動投稿
    if has_x:
        final_tweet = compose_final_tweet(posts[0], news_url)
        tweet_id = post_tweet(final_tweet) or ""
        if tweet_id:
            print(f"[X投稿完了] https://x.com/GAUCHE_cellist/status/{tweet_id}")
        else:
            print("[X投稿失敗] LINE通知にフォールバック")
    else:
        print("[X認証情報なし] LINE通知モードで動作")

    # LINE通知（投稿確認 or フォールバック）
    if line_token and line_user_id:
        message = build_line_message(posts, source, news_url, tweet_id)
        ok = send_line_message(line_token, line_user_id, message)
        print(f"[LINE通知{'完了' if ok else '失敗'}]")

    # ログ記録
    key = note_filename if note_filename else "rss"
    status = tweet_id if tweet_id else "line_notified"
    append_to_log(f"{key}\t{date.today()}\t{status}")


if __name__ == "__main__":
    main()
