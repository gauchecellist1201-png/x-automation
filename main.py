"""
毎日 JST 21:00 に最新AIニュースからバイラル投稿を生成し X に自動投稿するスクリプト
投稿後は LINE に「何を投稿したか」と全候補案を通知する
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date

from content_gen import generate_posts_from_notes, generate_posts_from_rss
from x_poster import post_tweet, upload_media_from_url

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


# ── ログ管理 ──────────────────────────────────────────────

def load_posted_log() -> set[str]:
    if not LOG_FILE.exists():
        return set()
    return set(LOG_FILE.read_text(encoding="utf-8").splitlines())


def append_to_log(source: str, tweet_id: str) -> None:
    today = date.today().isoformat()
    entry = f"{source}\t{today}\t{tweet_id}"
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_unposted_notes(posted: set[str]) -> list[Path]:
    if not NOTES_DIR.exists():
        return []
    posted_names = {e.split("\t")[0] for e in posted}
    return [p for p in NOTES_DIR.glob("*.md") if p.name not in posted_names]


# ── LINE 通知 ─────────────────────────────────────────────

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


def build_posted_notification(
    posted_text: str, all_candidates: list[str], tweet_id: str | None
) -> str:
    today = date.today().strftime("%Y/%m/%d")
    tweet_url = f"https://x.com/GAUCHE_cellist/status/{tweet_id}" if tweet_id else "（投稿失敗）"
    lines = [
        f"✅ X投稿完了 ({today})",
        f"🔗 {tweet_url}",
        "─" * 20,
        "【投稿した内容】",
        posted_text,
        "─" * 20,
        "【他の候補案】",
    ]
    for i, c in enumerate(all_candidates[1:], 2):
        lines.append(f"\n案{i}:\n{c}")
    return "\n".join(lines)


# ── メイン ────────────────────────────────────────────────

def run_from_notes(
    posted: set[str], line_token: str, line_user_id: str
) -> bool:
    """Note記事ベースで投稿。成功したら True を返す"""
    unposted = get_unposted_notes(posted)
    if not unposted:
        return False

    note_file = random.choice(unposted)
    note_text = note_file.read_text(encoding="utf-8")
    feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

    # NoteURLをファイル内から抽出（NOTE_URL: http... という行があれば使う）
    note_url = ""
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            note_url = line.split(":", 1)[1].strip()
            break

    posts = generate_posts_from_notes(note_text, feedback_text, note_url)
    if not posts:
        return False

    tweet_id = post_tweet(posts[0])
    notification = build_posted_notification(posts[0], posts, tweet_id)
    send_line_message(line_token, line_user_id, notification)
    append_to_log(note_file.name, tweet_id or "post_failed")
    print(f"[X投稿完了] Note: {note_file.name} / tweet_id={tweet_id}")
    return True


def run_from_rss(line_token: str, line_user_id: str) -> bool:
    """RSSニュースベースで投稿。成功したら True を返す"""
    posts, ogp_image_url = generate_posts_from_rss()
    if not posts:
        return False

    # OGP画像があればアップロード
    media_ids: list[int] | None = None
    if ogp_image_url:
        media_id = upload_media_from_url(ogp_image_url)
        if media_id:
            media_ids = [media_id]
            print(f"[画像添付] {ogp_image_url}")

    tweet_id = post_tweet(posts[0], media_ids=media_ids)
    notification = build_posted_notification(posts[0], posts, tweet_id)
    send_line_message(line_token, line_user_id, notification)
    append_to_log("rss", tweet_id or "post_failed")
    print(f"[X投稿完了] RSSニュース / tweet_id={tweet_id}")
    return True


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()

    # Note記事を優先、なければRSSニュース
    if run_from_notes(posted, line_token, line_user_id):
        return
    if run_from_rss(line_token, line_user_id):
        return

    print("投稿候補が生成できませんでした。")
    sys.exit(1)


if __name__ == "__main__":
    main()
