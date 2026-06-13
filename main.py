"""
毎日 JST 21:00 にバズりやすいAI投稿をX（Twitter）へ自動投稿し、
結果をLINEで通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss, generate_thread

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
X_USERNAME = "GAUCHE_cellist"

# スレッド投稿する確率（週2回程度 = 約30%）
THREAD_PROBABILITY = 0.3


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
    except Exception:
        return False


def _has_x_credentials() -> bool:
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    return all(os.environ.get(k) for k in required)


def post_to_x(tweets: list[str], use_thread: bool = False) -> tuple[bool, str]:
    """Xへ投稿。(成功フラグ, tweet_id or エラーメッセージ) を返す"""
    from x_post import post_tweet, post_thread, tweet_url

    try:
        if use_thread and len(tweets) >= 2:
            tweet_id = post_thread(tweets)
        else:
            tweet_id = post_tweet(tweets[0])

        if tweet_id:
            url = tweet_url(tweet_id, X_USERNAME)
            return True, url
        return False, "tweet_id が取得できませんでした"
    except Exception as e:
        return False, str(e)


def build_line_message(
    tweets: list[str],
    source: str,
    tweet_url: str = "",
    post_success: bool = False,
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    status = "✅ 自動投稿完了！" if post_success else "📝 投稿候補（手動投稿してください）"

    lines = [
        f"\n🤖 今日({today})のX投稿 [{source}]",
        status,
    ]
    if tweet_url:
        lines.append(f"🔗 {tweet_url}")
    lines.append("─" * 20)

    for i, t in enumerate(tweets[:3], 1):
        lines.append(f"\n【案{i}】\n{t}")
        lines.append("─" * 20)

    if not post_success:
        lines.append("\n⬆️ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    tweets: list[str] = []
    source = ""
    use_thread = random.random() < THREAD_PROBABILITY

    # Note記事から生成（未投稿ノートがある場合）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split(":", 1)[1].strip()
                break

        if use_thread:
            tweets = generate_thread(note_text[:500], note_text)
        else:
            tweets = generate_posts_from_notes(note_text, feedback_text, note_url)

        source = f"Note: {note_file.stem}"
        log_key = note_file.name

    # RSSニュースから生成
    if not tweets:
        if use_thread:
            rss_tweets, rss_source = generate_posts_from_rss()
            if rss_tweets:
                tweets = generate_thread(rss_tweets[0])
        else:
            tweets, rss_source = generate_posts_from_rss()
        source = rss_source
        log_key = "rss"

    if not tweets:
        print("投稿候補が生成できませんでした。")
        sys.exit(1)

    # X へ自動投稿
    post_success = False
    x_url = ""
    if _has_x_credentials():
        post_success, result = post_to_x(tweets, use_thread=use_thread)
        if post_success:
            x_url = result
            print(f"[X投稿完了] {x_url}")
            append_to_log(f"{log_key}\t{date.today()}\t{x_url}")
        else:
            print(f"[X投稿失敗] {result}")
    else:
        print("[X投稿スキップ] X API認証情報が未設定です")

    # LINE通知（任意）
    if line_token and line_user_id:
        msg = build_line_message(tweets, source, x_url, post_success)
        if send_line_message(line_token, line_user_id, msg):
            print("[LINE通知完了]")
            if not post_success:
                append_to_log(f"{log_key}\t{date.today()}\tline_notified")
        else:
            print("[LINE通知失敗]")
    elif not post_success:
        # LINE もX も使えない場合は標準出力で確認
        print(f"\n--- 投稿案 ({source}) ---")
        for i, t in enumerate(tweets[:3], 1):
            print(f"【案{i}】 {t}")


if __name__ == "__main__":
    main()
