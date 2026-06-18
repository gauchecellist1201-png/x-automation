"""
毎日21:00 JST にAI投稿を自動生成・X投稿・LINE通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date, timedelta
from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    select_best_tweet,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
NOTE_REUSE_DAYS = 30  # 同じNoteを再利用するまでの日数


def load_log_entries() -> list[tuple[str, str, str]]:
    """ログを解析して (filename, date_str, status) のリストを返す"""
    if not LOG_FILE.exists():
        return []
    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        filename = parts[0] if len(parts) > 0 else ""
        date_str = parts[1] if len(parts) > 1 else ""
        status = parts[2] if len(parts) > 2 else ""
        if filename:
            entries.append((filename, date_str, status))
    return entries


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_eligible_notes() -> list[Path]:
    """NOTE_REUSE_DAYS以上前に使用した（または未使用の）Noteファイルを返す"""
    if not NOTES_DIR.exists():
        return []

    cutoff = date.today() - timedelta(days=NOTE_REUSE_DAYS)
    entries = load_log_entries()

    # ファイル名 -> 最終使用日
    last_used: dict[str, date] = {}
    for filename, date_str, _ in entries:
        try:
            d = date.fromisoformat(date_str)
            if filename not in last_used or d > last_used[filename]:
                last_used[filename] = d
        except ValueError:
            pass

    eligible = []
    for p in NOTES_DIR.glob("*.md"):
        last = last_used.get(p.name)
        if last is None or last <= cutoff:
            eligible.append(p)
    return eligible


def post_to_x(tweet_text: str) -> str | None:
    """X (Twitter) API v2 で投稿し、tweet_id を返す"""
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=os.environ["TWITTER_API_KEY"],
            consumer_secret=os.environ["TWITTER_API_SECRET"],
            access_token=os.environ["TWITTER_ACCESS_TOKEN"],
            access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
        )
        response = client.create_tweet(text=tweet_text)
        if response.data:
            return str(response.data["id"])
    except Exception as e:
        print(f"[X投稿エラー] {e}")
    return None


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
        print(f"[LINE通知エラー] {e}")
        return False


def build_posted_message(tweet: str, tweet_id: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    tweet_url = f"https://x.com/GAUCHE_cellist/status/{tweet_id}"
    return (
        f"\n✅ 今日({today})のX投稿完了！\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{tweet}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📎 {tweet_url}\n"
        f"🔍 ソース: {source}"
    )


def build_candidates_message(posts: list[str], source: str) -> str:
    """X投稿失敗時のフォールバック: 候補一覧をLINEに送る"""
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "（⚠️ 自動投稿に失敗しました。手動でお願いします）",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def has_twitter_credentials() -> bool:
    keys = ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"]
    return all(os.environ.get(k) for k in keys)


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    has_line = bool(line_token and line_user_id)
    use_twitter = has_twitter_credentials()

    posts: list[str] = []
    source = ""
    log_key = ""

    # Note記事から生成（30日以上使っていないものを優先）
    eligible_notes = get_eligible_notes()
    if eligible_notes:
        note_file = random.choice(eligible_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        source = f"Note: {note_file.stem}"
        log_key = note_file.name

    # Note生成に失敗 or 対象なし → RSSニュースから生成
    if not posts:
        rss_posts, news_item = generate_posts_from_rss()
        posts = rss_posts
        source = news_item.source if news_item else "AIニュース"
        log_key = "rss"

    if not posts:
        print("投稿候補が生成できませんでした。")
        sys.exit(1)

    best = select_best_tweet(posts)
    if not best:
        print("ベスト案の選択に失敗しました。")
        sys.exit(1)

    print(f"[生成完了] {best[:60]}...")

    # X自動投稿
    tweet_id = None
    if use_twitter:
        tweet_id = post_to_x(best)

    if tweet_id:
        append_to_log(f"{log_key}\t{date.today()}\t{tweet_id}")
        print(f"[X投稿完了] ID: {tweet_id}")
        if has_line:
            send_line_message(line_token, line_user_id, build_posted_message(best, tweet_id, source))
    else:
        # X投稿なし（未設定 or 失敗）→ LINEに候補を送る
        append_to_log(f"{log_key}\t{date.today()}\tline_notified")
        print("[X投稿スキップ] LINEに投稿案を通知します。")
        if has_line:
            ok = send_line_message(line_token, line_user_id, build_candidates_message(posts, source))
            if ok:
                print("[LINE通知完了]")
            else:
                print("[LINE通知失敗]")
        else:
            print(f"投稿案:\n{best}")


if __name__ == "__main__":
    main()
