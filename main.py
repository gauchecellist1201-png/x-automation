"""
毎日21:00 JST にAI投稿案を生成してXに自動投稿し、LINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
X_ACCOUNT = "GAUCHE_cellist"


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
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    return response.status_code == 200


def has_x_credentials() -> bool:
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    return all(os.environ.get(k) for k in required)


def try_post_to_x(text: str) -> str | None:
    """X APIで投稿を試みる。認証情報がない場合やエラー時はNoneを返す"""
    if not has_x_credentials():
        print("⚠️ X API認証情報が未設定のためスキップ")
        return None
    try:
        from x_poster import post_to_x
        return post_to_x(text)
    except ImportError:
        print("⚠️ tweepyが未インストールのためXへの投稿をスキップ")
        return None
    except Exception as e:
        print(f"⚠️ X投稿エラー: {e}")
        return None


def build_line_message(posts: list[str], source: str, tweet_id: str | None) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n今日({today})のX投稿 [{source}]"]

    if tweet_id:
        tweet_url = f"https://x.com/{X_ACCOUNT}/status/{tweet_id}"
        lines.append(f"✅ 自動投稿済み: {tweet_url}")
        lines.append("─" * 20)
        for i, post in enumerate(posts[:3], 1):
            marker = "← 投稿済み" if i == 1 else ""
            lines.append(f"\n【案{i}】{marker}\n{post}")
            lines.append("─" * 20)
        lines.append("\n問題があればXから削除してください。")
    else:
        lines.append("─" * 20)
        for i, post in enumerate(posts[:3], 1):
            lines.append(f"\n【案{i}】\n{post}")
            lines.append("─" * 20)
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")

    return "\n".join(lines)


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = ""
    log_key = "rss"

    # 優先1: Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            source = f"Note: {note_file.stem}"
            log_key = note_file.name

    # 優先2: RSSニュースから生成
    if not posts:
        posts = generate_posts_from_rss()
        source = "AIニュース"
        log_key = "rss"

    if not posts:
        print("投稿候補がありませんでした。")
        sys.exit(0)

    # X自動投稿（認証情報がある場合）
    tweet_id = try_post_to_x(posts[0])

    # LINE通知
    if line_token and line_user_id:
        message = build_line_message(posts, source, tweet_id)
        if send_line_message(line_token, line_user_id, message):
            status = "x_posted_line_notified" if tweet_id else "line_notified"
            append_to_log(f"{log_key}\t{date.today()}\t{status}")
            print(f"[完了] {source} / X投稿: {'済' if tweet_id else '未'} / LINE通知: 済")
            return

    # LINE通知なし・X投稿のみ
    if tweet_id:
        append_to_log(f"{log_key}\t{date.today()}\tx_posted")
        print(f"[完了] {source} / X投稿: 済")
        return

    print("投稿も通知も完了しませんでした。")
    sys.exit(1)


if __name__ == "__main__":
    main()
