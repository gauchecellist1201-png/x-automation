"""
毎日 21:00 JST に AI 投稿を生成し X に自動投稿するスクリプト。
X 認証情報がない場合は LINE 通知のみにフォールバックする。
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss
from x_poster import post_tweet, get_tweet_url, x_credentials_available

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
    # ログに「note投稿済み」が記録されていないファイルを返す
    posted_stems = {e.split("\t")[0] for e in posted}
    return [p for p in NOTES_DIR.glob("*.md") if p.name not in posted_stems]


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


def build_line_message_posted(tweet_text: str, tweet_url: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    return (
        f"\n✅ X投稿完了 ({today})\n"
        f"━━━━━━━━━━━━\n"
        f"[{source}]\n\n"
        f"{tweet_text}\n"
        f"━━━━━━━━━━━━\n"
        f"🔗 {tweet_url}"
    )


def build_line_message_candidates(posts: list[str], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "━━━━━━━━━━━━",
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("━━━━━━━━━━━━")
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def try_post_to_x(posts: list[str]) -> str | None:
    """複数の投稿候補から最初に成功した投稿IDを返す。"""
    for post in posts:
        tweet_id = post_tweet(post)
        if tweet_id:
            return tweet_id
    return None


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    use_line = bool(line_token and line_user_id)
    use_x = x_credentials_available()

    if not use_x and not use_line:
        print("[エラー] X または LINE の認証情報が設定されていません。")
        sys.exit(1)

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # --- Note 記事から生成 ---
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        # naoki_profile.md の NOTE_URL を抽出
        note_url_match = __import__("re").search(r"NOTE_URL:\s*(\S+)", note_text)
        note_url = note_url_match.group(1) if note_url_match else ""
        posts = generate_posts_from_notes(note_text, feedback_text, note_url)

        if posts:
            source = f"Note: {note_file.stem}"
            if use_x:
                tweet_id = try_post_to_x(posts)
                if tweet_id:
                    tweet_url = get_tweet_url(tweet_id)
                    append_to_log(f"{note_file.name}\t{date.today()}\t{tweet_id}")
                    print(f"[X投稿完了] {source} → {tweet_url}")
                    if use_line:
                        msg = build_line_message_posted(posts[0], tweet_url, source)
                        send_line_message(line_token, line_user_id, msg)
                    return
            # X 不使用 or 失敗 → LINE 候補通知
            if use_line:
                msg = build_line_message_candidates(posts, source)
                if send_line_message(line_token, line_user_id, msg):
                    append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                    print(f"[LINE通知完了] {source}")
                    return

    # --- RSS ニュースから生成 ---
    posts, article_url = generate_posts_from_rss()
    if posts:
        source = "AIニュース"
        if use_x:
            tweet_id = try_post_to_x(posts)
            if tweet_id:
                tweet_url = get_tweet_url(tweet_id)
                append_to_log(f"rss\t{date.today()}\t{tweet_id}")
                print(f"[X投稿完了] {source} → {tweet_url}")
                if use_line:
                    msg = build_line_message_posted(posts[0], tweet_url, source)
                    send_line_message(line_token, line_user_id, msg)
                return
        if use_line:
            msg = build_line_message_candidates(posts, source)
            if send_line_message(line_token, line_user_id, msg):
                append_to_log(f"rss\t{date.today()}\tline_notified")
                print("[LINE通知完了] RSSニュース")
                return

    print("[警告] 投稿候補の生成または通知に失敗しました。")
    sys.exit(1)


if __name__ == "__main__":
    main()
