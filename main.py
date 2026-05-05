"""
毎日 JST 21:00 にバイラルAI投稿を生成→X自動投稿→LINEに確認通知
"""

import os
import sys
import random
import requests
import logging
from pathlib import Path
from datetime import date
from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    select_best_post,
)
from tweet_poster import post_tweet, is_x_api_configured

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

DRY_RUN = "--dry-run" in sys.argv


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
    except Exception as e:
        logger.error(f"LINE送信エラー: {e}")
        return False


def build_line_posted_message(tweet_text: str, tweet_url: str, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    return (
        f"\n✅ X投稿完了 ({today}) [{source}]\n"
        f"{'─' * 20}\n"
        f"{tweet_text}\n"
        f"{'─' * 20}\n"
        f"🔗 {tweet_url}"
    )


def build_line_candidates_message(posts: list[str], source: str) -> str:
    """X API未設定時: 候補をLINEに送って手動投稿を促す"""
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


def _generate_candidates(posted: set[str]) -> tuple[list[str], str]:
    """
    Returns (candidates, source_label)
    """
    unposted = get_unposted_notes(posted)
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        # NoteのURLをプロフィールから抽出（あれば）
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split("NOTE_URL:", 1)[1].strip()
        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            return posts, f"Note:{note_file.stem}"

    posts = generate_posts_from_rss()
    if posts:
        return posts, "AIニュース"

    return [], "なし"


def main() -> None:
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    posted = load_posted_log()
    candidates, source = _generate_candidates(posted)

    if not candidates:
        logger.warning("投稿候補が生成できませんでした")
        sys.exit(0)

    logger.info(f"[生成完了] {len(candidates)}案 (ソース: {source})")
    for i, c in enumerate(candidates, 1):
        logger.info(f"  案{i}: {c}")

    # バイラリティスコアリングで最良案を選ぶ
    best = select_best_post(candidates)
    if not best:
        best = candidates[0]

    logger.info(f"[最優秀案] {best}")

    if DRY_RUN:
        print(f"[DRY RUN] 投稿予定:\n{best}")
        return

    # X API 自動投稿
    if is_x_api_configured():
        try:
            result = post_tweet(best)
            log_entry = f"x_posted\t{date.today()}\t{result['id']}\t{source}"
            append_to_log(log_entry)
            logger.info(f"[X投稿完了] {result['url']}")

            # LINE確認通知
            if line_token and line_user_id:
                msg = build_line_posted_message(best, result["url"], source)
                send_line_message(line_token, line_user_id, msg)
            return

        except Exception as e:
            logger.error(f"X投稿エラー: {e}。LINEに候補を送ります。")

    # X API未設定 or エラー時: LINEに候補を送って手動投稿
    if line_token and line_user_id:
        msg = build_line_candidates_message(candidates[:3], source)
        if send_line_message(line_token, line_user_id, msg):
            append_to_log(f"line_notified\t{date.today()}\t{source}")
            logger.info("[LINE通知完了]")
    else:
        print("\n=== 今日の投稿案 ===")
        for i, post in enumerate(candidates[:3], 1):
            print(f"\n【案{i}】\n{post}")


if __name__ == "__main__":
    main()
