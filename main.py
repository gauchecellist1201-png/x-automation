"""
毎日 JST 21:00 にAI関連投稿をX(Twitter)に自動投稿し、LINEで結果を通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss, select_best_post

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> set[str]:
    """ログからファイル名のセットを返す（重複投稿防止）"""
    if not LOG_FILE.exists():
        return set()
    posted = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            parts = line.split("\t")
            if parts:
                posted.add(parts[0])
    return posted


def append_to_log(filename: str, tweet_id: str = "line_notified") -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{filename}\t{date.today()}\t{tweet_id}\n")


def get_unposted_notes(posted: set[str]) -> list[Path]:
    if not NOTES_DIR.exists():
        return []
    unposted = [p for p in NOTES_DIR.glob("*.md") if p.name not in posted]
    if not unposted:
        # 全ノートを使い切ったらリセットして再利用
        return list(NOTES_DIR.glob("*.md"))
    return unposted


def _has_x_credentials() -> bool:
    required = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
    return all(os.environ.get(k) for k in required)


def _post_to_x(text: str) -> str | None:
    from x_poster import post_tweet
    try:
        return post_tweet(text)
    except Exception as e:
        print(f"[X投稿エラー] {e}")
        return None


def _fetch_viral_examples() -> list[str]:
    if not _has_x_credentials():
        return []
    from x_poster import fetch_viral_ai_tweets
    try:
        return fetch_viral_ai_tweets()
    except Exception:
        return []


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


def build_line_message_posted(tweet_text: str, tweet_url: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    return (
        f"\n✅ X投稿完了！({today}) [{source}]\n"
        f"{'─' * 20}\n"
        f"{tweet_text}\n"
        f"{'─' * 20}\n"
        f"🔗 {tweet_url}"
    )


def build_line_message_candidates(posts: list[str], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    # バズりツイートを取得（X APIある場合のみ）
    viral_examples = _fetch_viral_examples()
    if viral_examples:
        print(f"[バズりツイート取得] {len(viral_examples)}件")

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = ""
    tweet_url_hint = ""

    # Note記事から生成
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split("NOTE_URL:", 1)[1].strip()
                break
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text, note_url, viral_examples)
        source = f"Note: {note_file.stem}"
        tweet_url_hint = note_url

        if posts:
            best = select_best_post(posts)
            if _has_x_credentials():
                tweet_id = _post_to_x(best)
                if tweet_id:
                    from x_poster import build_tweet_url
                    tweet_url = build_tweet_url(tweet_id)
                    msg = build_line_message_posted(best, tweet_url, source)
                    send_line_message(line_token, line_user_id, msg)
                    append_to_log(note_file.name, tweet_id)
                    print(f"[X投稿完了] {tweet_url}")
                    return
            # X認証なし → 候補をLINEに送信
            msg = build_line_message_candidates(posts, source)
            send_line_message(line_token, line_user_id, msg)
            append_to_log(note_file.name)
            print(f"[LINE通知完了] Note: {note_file.name}")
            return

    # RSSニュースから生成
    posts, top_url = generate_posts_from_rss(viral_examples)
    source = "AIニュース"
    if posts:
        best = select_best_post(posts)
        if top_url:
            # URL付与（280文字以内に収まる場合）
            candidate = f"{best}\n{top_url}"
            if len(candidate) <= 280:
                best = candidate

        if _has_x_credentials():
            tweet_id = _post_to_x(best)
            if tweet_id:
                from x_poster import build_tweet_url
                tweet_url = build_tweet_url(tweet_id)
                msg = build_line_message_posted(best, tweet_url, source)
                send_line_message(line_token, line_user_id, msg)
                append_to_log("rss", tweet_id)
                print(f"[X投稿完了] {tweet_url}")
                return

        msg = build_line_message_candidates(posts, source)
        send_line_message(line_token, line_user_id, msg)
        append_to_log("rss")
        print("[LINE通知完了] RSSニュース")
        return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
