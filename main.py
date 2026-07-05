"""
毎日21:00 JST にAI投稿案を生成し、X自動投稿 + LINEで確認通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date, timedelta
from content_gen import generate_posts_from_notes, generate_posts_from_rss

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
NOTE_REUSE_DAYS = 30  # Note記事は30日経過後に再利用可能


def load_posted_log() -> list[tuple[str, date, str]]:
    """ポスト済みログを (filename, date, status) のリストとして読み込む"""
    if not LOG_FILE.exists():
        return []
    entries = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        try:
            entries.append((parts[0], date.fromisoformat(parts[1]), parts[2]))
        except ValueError:
            continue
    return entries


def append_to_log(filename: str, status: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{filename}\t{date.today()}\t{status}\n")


def get_available_notes(log: list[tuple[str, date, str]]) -> list[Path]:
    """30日以内に使用していないNote記事を返す"""
    if not NOTES_DIR.exists():
        return []
    cutoff = date.today() - timedelta(days=NOTE_REUSE_DAYS)
    recently_used = {
        filename for filename, post_date, _ in log
        if post_date >= cutoff and filename != "rss"
    }
    return [p for p in NOTES_DIR.glob("*.md") if p.name not in recently_used]


def _extract_note_url(note_text: str) -> str:
    """Note記事本文から NOTE_URL: を抽出"""
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split(":", 1)[1].strip()
    return ""


def post_to_x(tweet_text: str) -> str | None:
    """X API v2 でツイートを投稿し、ツイートIDを返す（認証情報がなければNone）"""
    try:
        import tweepy
    except ImportError:
        print("[X投稿スキップ] tweepyがインストールされていません")
        return None

    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_secret = os.environ.get("X_ACCESS_SECRET")

    if not all([api_key, api_secret, access_token, access_secret]):
        print("[X投稿スキップ] X API認証情報が未設定（LINE通知のみ実行）")
        return None

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )
    response = client.create_tweet(text=tweet_text)
    tweet_id = str(response.data["id"])
    print(f"[X投稿完了] https://x.com/GAUCHE_cellist/status/{tweet_id}")
    return tweet_id


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


def build_line_message(posts: list[str], source: str, posted_tweet: str | None = None) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = []

    if posted_tweet:
        lines += [
            f"\n✅ X投稿完了！({today}) [{source}]",
            "─" * 22,
            f"\n【投稿済み】\n{posted_tweet}",
            "─" * 22,
            "\n📋 他の候補案（参考）",
        ]
        remaining = posts[1:4]
    else:
        lines += [
            f"\n🤖 今日({today})のX投稿案 [{source}]",
            "─" * 22,
        ]
        remaining = posts[:3]

    for i, post in enumerate(remaining, 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 22)

    if not posted_tweet:
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")

    return "\n".join(lines)


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")

    log = load_posted_log()
    available_notes = get_available_notes(log)

    posts: list[str] = []
    source = ""
    log_key = ""

    # Note記事から生成（30日以内に未使用のものがある場合）
    if available_notes:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_url = _extract_note_url(note_text)
        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        source = f"Note: {note_file.stem}"
        log_key = note_file.name

    # RSSニュースから生成（Note未使用 or 生成失敗時）
    if not posts:
        posts, _ = generate_posts_from_rss()
        source = "AIニュース"
        log_key = "rss"

    if not posts:
        print("投稿候補が生成できませんでした。")
        sys.exit(0)

    # X自動投稿（バイラルスコア1位を投稿）
    tweet_id = None
    try:
        tweet_id = post_to_x(posts[0])
    except Exception as e:
        print(f"[X投稿エラー] {e}")

    log_status = tweet_id if tweet_id else "line_notified"
    append_to_log(log_key, log_status)

    # LINE通知
    if line_token and line_user_id:
        message = build_line_message(posts, source, posts[0] if tweet_id else None)
        ok = send_line_message(line_token, line_user_id, message)
        if ok:
            print(f"[LINE通知完了] {source}")
        else:
            print(f"[LINE通知失敗] {source}")
    else:
        print("[LINE通知スキップ] 認証情報が未設定")

    print(f"[処理完了] source={source}, x_posted={bool(tweet_id)}")


if __name__ == "__main__":
    main()
