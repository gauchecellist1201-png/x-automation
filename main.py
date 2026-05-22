"""
毎日AIバイラル投稿を生成し、X(Twitter)に自動投稿 + LINEに結果通知
ターゲット: ビジネス層向けX自動運用 @GAUCHE_cellist
"""
import os
import random
import sys
from datetime import date
from pathlib import Path

import requests

from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    generate_viral_thread,
)
from viral_analyzer import fetch_trends
from x_poster import (
    get_og_image_url,
    has_x_credentials,
    post_thread,
    post_tweet,
    upload_image,
)

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


def send_line(token: str, user_id: str, message: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    try:
        r = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
        return r.status_code == 200
    except requests.RequestException:
        return False


def _line_posted(tweet_text: str, tweet_id: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    return (
        f"\n✅ [{today}] X投稿完了 [{source}]\n"
        f"{'─' * 20}\n"
        f"{tweet_text}\n"
        f"{'─' * 20}\n"
        f"🔗 https://x.com/GAUCHE_cellist/status/{tweet_id}\n"
    )


def _line_candidates(posts: list[str], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:3], 1):
        lines.append(f"\n【案{i}】\n{post}")
        lines.append("─" * 20)
    lines.append("\n💡 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def _extract_note_url(note_text: str) -> str:
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split(":", 1)[1].strip()
    return ""


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")
    x_enabled = has_x_credentials()

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    posts: list[str] = []
    source = ""
    note_file: Path | None = None
    article_url = ""

    # ── 1. Note記事から生成（優先） ──────────────────────────
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = (
            FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        )
        note_url = _extract_note_url(note_text)
        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        source = f"Note: {note_file.stem}"
        article_url = note_url

    # ── 2. RSSニュースから生成（フォールバック） ─────────────
    if not posts:
        trends = fetch_trends(max_items=5)
        posts = generate_posts_from_rss()
        source = "AIニュース"
        article_url = trends[0].url if trends else ""

    # ── 3. スレッド生成（最終フォールバック） ─────────────────
    if not posts:
        thread = generate_viral_thread()
        if thread and x_enabled:
            trends = fetch_trends(max_items=1)
            img_url = get_og_image_url(trends[0].url) if trends else None
            media_id = upload_image(img_url) if img_url else None

            ids = post_thread(thread, media_id=media_id)
            if ids:
                if line_token and line_user_id:
                    send_line(line_token, line_user_id, _line_posted(thread[0], ids[0], "スレッド"))
                log_key = note_file.name if note_file else "thread"
                append_to_log(f"{log_key}\t{date.today()}\tx_posted_thread\t{ids[0]}")
                print(f"[X投稿完了] スレッド: {ids[0]}")
                return
        if not posts and not thread:
            print("投稿候補がありませんでした。")
            sys.exit(0)

    if not posts:
        print("投稿候補が生成できませんでした。")
        sys.exit(1)

    # ── X自動投稿 ──────────────────────────────────────────────
    best_post = posts[0]

    if x_enabled:
        # OGP画像の取得・アップロード
        img_url = get_og_image_url(article_url) if article_url else None
        media_id = upload_image(img_url) if img_url else None

        tweet_id = post_tweet(best_post, media_id=media_id)
        if tweet_id:
            if line_token and line_user_id:
                send_line(line_token, line_user_id, _line_posted(best_post, tweet_id, source))
            log_key = note_file.name if note_file else "rss"
            append_to_log(f"{log_key}\t{date.today()}\tx_posted\t{tweet_id}")
            print(f"[X投稿完了] {source}: {tweet_id}")
            return
        else:
            print("[X投稿失敗] LINE通知にフォールバック")

    # ── LINE通知（X投稿できない場合） ─────────────────────────
    if line_token and line_user_id:
        msg = _line_candidates(posts, source)
        if send_line(line_token, line_user_id, msg):
            log_key = note_file.name if note_file else "rss"
            append_to_log(f"{log_key}\t{date.today()}\tline_notified")
            print(f"[LINE通知完了] {source}")
            return

    print("X投稿もLINE通知も失敗しました。")
    sys.exit(1)


if __name__ == "__main__":
    main()
