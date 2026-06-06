"""
毎日 JST 21:00 にAI投稿案を生成し、X（Twitter）に自動投稿 + LINEに通知するスクリプト

動作モード:
  - X_AUTO_POST=true 環境変数が設定されている場合、X API で自動投稿
  - それ以外は LINE 通知のみ（手動投稿）
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
    generate_thread_from_rss,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> set[str]:
    """投稿済みファイル名のセットを返す（タブ区切りの1カラム目のみ抽出）"""
    if not LOG_FILE.exists():
        return set()
    posted = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            filename = line.split("\t")[0]
            posted.add(filename)
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


def build_line_message(posts: list[str], source: str, posted_ids: list[str] | None = None) -> str:
    today = date.today().strftime("%Y/%m/%d")
    auto_posted = bool(posted_ids)
    status = "✅ X投稿済み" if auto_posted else "📋 投稿案"

    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        f"ステータス: {status}",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        if auto_posted and i == 1 and posted_ids:
            lines.append(f"🔗 https://x.com/i/web/status/{posted_ids[0]}")
        lines.append("─" * 20)

    if not auto_posted:
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def build_line_message_thread(thread: list[str], source: str, thread_ids: list[str] | None = None) -> str:
    today = date.today().strftime("%Y/%m/%d")
    auto_posted = bool(thread_ids)
    status = "✅ スレッドX投稿済み" if auto_posted else "📋 スレッド投稿案"

    lines = [
        f"\n🤖 今日({today})のXスレッド [{source}]",
        f"ステータス: {status}",
        "─" * 20,
    ]
    for i, tweet in enumerate(thread, 1):
        lines.append(f"\n[{i}/{len(thread)}]\n{tweet}")
    lines.append("─" * 20)

    if auto_posted and thread_ids:
        lines.append(f"\n🔗 https://x.com/i/web/status/{thread_ids[0]}")
    elif not auto_posted:
        lines.append("\n✅ 上記スレッドをXに順番に投稿してください！")
    return "\n".join(lines)


def try_x_auto_post(posts: list[str]) -> list[str]:
    """X自動投稿を試みる。成功した tweet_id リストを返す。失敗時は空リスト。"""
    if os.environ.get("X_AUTO_POST", "").lower() != "true":
        return []
    try:
        from twitter_client import post_tweet
        tweet_id = post_tweet(posts[0])
        if tweet_id:
            print(f"[X投稿成功] tweet_id={tweet_id}")
            return [tweet_id]
    except Exception as e:
        print(f"[X投稿スキップ] {e}")
    return []


def try_x_thread_post(thread: list[str]) -> list[str]:
    """Xスレッド自動投稿を試みる。成功した tweet_id リストを返す。失敗時は空リスト。"""
    if os.environ.get("X_AUTO_POST", "").lower() != "true":
        return []
    try:
        from twitter_client import post_thread
        ids = post_thread(thread)
        if ids:
            print(f"[Xスレッド投稿成功] {len(ids)}件 最初のID={ids[0]}")
            return ids
    except Exception as e:
        print(f"[Xスレッド投稿スキップ] {e}")
    return []


def try_fetch_viral_tweets() -> list[str]:
    """バズっているAIツイートを取得（X API アクセスが不十分な場合は空リスト）"""
    try:
        from twitter_client import fetch_viral_ai_tweets
        tweets = fetch_viral_ai_tweets()
        if tweets:
            print(f"[バズツイート取得] {len(tweets)}件")
        return tweets
    except Exception:
        return []


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    use_line = bool(line_token and line_user_id)

    viral_tweets = try_fetch_viral_tweets()
    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            posted_ids = try_x_auto_post(posts)
            message = build_line_message(posts, f"Note: {note_file.stem}", posted_ids)
            log_status = "x_posted" if posted_ids else "line_notified"
            if use_line:
                send_line_message(line_token, line_user_id, message)
            append_to_log(f"{note_file.name}\t{date.today()}\t{log_status}")
            print(f"[完了] Note: {note_file.name} → {log_status}")
            return

    # スレッド形式を試みる
    thread = generate_thread_from_rss(viral_tweets)
    if len(thread) >= 2:
        thread_ids = try_x_thread_post(thread)
        message = build_line_message_thread(thread, "AIニュース スレッド", thread_ids)
        log_status = "x_thread_posted" if thread_ids else "line_notified"
        if use_line:
            send_line_message(line_token, line_user_id, message)
        append_to_log(f"rss_thread\t{date.today()}\t{log_status}")
        print(f"[完了] RSSスレッド → {log_status}")
        return

    # 単一ツイート
    posts = generate_posts_from_rss(viral_tweets)
    if posts:
        posted_ids = try_x_auto_post(posts)
        message = build_line_message(posts, "AIニュース", posted_ids)
        log_status = "x_posted" if posted_ids else "line_notified"
        if use_line:
            send_line_message(line_token, line_user_id, message)
        append_to_log(f"rss\t{date.today()}\t{log_status}")
        print(f"[完了] RSSニュース → {log_status}")
        return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
