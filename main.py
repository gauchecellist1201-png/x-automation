"""
毎日 JST 21:00 にバズりやすいAI投稿を生成してXに自動投稿するスクリプト
投稿後にLINEへ確認通知を送る
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
    fetch_ogp_image,
    pick_best,
)
from x_poster import post_tweet, upload_image

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
NOTE_URL = "https://note.com/naokiide/n/nfd6c82261b75"


def load_posted_log() -> dict[str, str]:
    """ログをfilename -> dateのマップとして返す（重複利用判定用）"""
    if not LOG_FILE.exists():
        return {}
    result: dict[str, str] = {}
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            result[parts[0]] = parts[1]
    return result


def append_to_log(filename: str, tweet_id: str) -> None:
    today = date.today().isoformat()
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{filename}\t{today}\t{tweet_id}\n")


def get_unposted_notes(posted_map: dict[str, str]) -> list[Path]:
    """今日まだ使っていないNoteファイルを返す"""
    if not NOTES_DIR.exists():
        return []
    today = date.today().isoformat()
    return [
        p
        for p in NOTES_DIR.glob("*.md")
        if posted_map.get(p.name) != today
    ]


def send_line_notification(token: str, user_id: str, message: str) -> bool:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    resp = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
    return resp.status_code == 200


def build_line_notification(posted_text: str, tweet_id: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    url = f"https://x.com/GAUCHE_cellist/status/{tweet_id}" if tweet_id else "（投稿失敗）"
    return (
        f"\n🤖 {today} のX投稿完了 [{source}]\n"
        f"{'─'*20}\n"
        f"{posted_text}\n"
        f"{'─'*20}\n"
        f"🔗 {url}"
    )


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    posted_map = load_posted_log()
    feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

    tweet_text: str = ""
    source: str = ""
    article_url: str = ""
    image_bytes: bytes | None = None

    # 1. Note記事から生成（まだ今日使っていないファイルがあれば）
    unposted = get_unposted_notes(posted_map)
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        candidates = generate_posts_from_notes(note_text, feedback_text, NOTE_URL)
        if candidates:
            tweet_text = pick_best(candidates)
            source = f"Note:{note_file.stem}"

    # 2. RSSニュースから生成（fallback）
    if not tweet_text:
        candidates, article_url, image_url = generate_posts_from_rss()
        if candidates:
            tweet_text = pick_best(candidates)
            source = "AIニュース"
            # OGP画像を取得
            if article_url:
                image_bytes = fetch_ogp_image(article_url)

    if not tweet_text:
        print("投稿候補を生成できませんでした。")
        sys.exit(1)

    # 3. X に投稿
    media_id = None
    if image_bytes:
        media_id = upload_image(image_bytes)

    tweet_id = post_tweet(tweet_text, media_id=media_id)

    # 4. ログ記録
    log_key = source if source.startswith("Note:") else "rss"
    append_to_log(log_key, tweet_id or "failed")

    # 5. LINE通知
    if line_token and line_user_id:
        msg = build_line_notification(tweet_text, tweet_id or "", source)
        send_line_notification(line_token, line_user_id, msg)
        print(f"[LINE通知完了]")

    if tweet_id:
        print(f"[完了] {source}: {tweet_text[:60]}...")
    else:
        print("[警告] X投稿に失敗しましたが処理を続行しました")
        sys.exit(1)


if __name__ == "__main__":
    main()
