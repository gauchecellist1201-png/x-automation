"""
毎日21:00 JST にAI投稿を自動生成 → X投稿 → LINE通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date

import x_poster
from content_gen import generate_from_rss, generate_from_notes, generate_original_insight

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
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


def send_line_message(message: str) -> bool:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("[LINE] 環境変数未設定のためスキップ")
        return False
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
    return response.status_code == 200


def build_line_message(content: dict, tweet_id: str | None, source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [f"\n🤖 {today} X投稿レポート [{source}]", "─" * 22]

    if tweet_id:
        url = x_poster.tweet_url(tweet_id)
        lines.append(f"\n✅ 投稿完了！\n{url}")
        lines.append("─" * 22)

    backup = content.get("tweets", [])[1:]  # 2番目以降を候補として表示
    if backup:
        lines.append("\n📋 追加投稿候補:")
        for i, t in enumerate(backup, 1):
            lines.append(f"\n【候補{i}】\n{t}")
            lines.append("─" * 22)

    thread = content.get("thread", [])
    if thread:
        lines.append("\n🧵 スレッド案（手動投稿用）:")
        for i, t in enumerate(thread, 1):
            lines.append(f"  {i}/{len(thread)}: {t}")
        lines.append("─" * 22)

    image_suggestion = content.get("image", "")
    if image_suggestion:
        lines.append(f"\n🖼️ 画像提案: {image_suggestion}")

    pattern = content.get("pattern", "")
    if pattern:
        lines.append(f"📊 使用パターン: {pattern}")

    if not tweet_id:
        lines.append("\n⚠️ X自動投稿失敗 — 上記の候補を手動で投稿してください")

    return "\n".join(lines)


def run() -> None:
    posted = load_posted_log()

    # Note記事 → RSSニュース の順で素材を選択
    content: dict | None = None
    source = ""

    unposted = get_unposted_notes(posted)
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split(":", 1)[1].strip()
                break
        content = generate_from_notes(note_text, note_url)
        source = f"Note:{note_file.stem}"

    if not content or not content.get("tweets"):
        content = generate_from_rss()
        source = "RSSニュース"

    if not content or not content.get("tweets"):
        content = generate_original_insight()
        source = "オリジナル洞察"

    if not content or not content.get("tweets"):
        print("投稿候補を生成できませんでした。")
        sys.exit(1)

    best_tweet = content["tweets"][0]
    tweet_id: str | None = None

    # X自動投稿
    if x_poster.is_configured():
        tweet_id = x_poster.post_tweet(best_tweet)
        if tweet_id:
            print(f"[X投稿完了] {x_poster.tweet_url(tweet_id)}")
            append_to_log(f"{source}\t{date.today()}\t{tweet_id}")
        else:
            print("[X投稿失敗] LINE通知に切り替え")
            append_to_log(f"{source}\t{date.today()}\tx_failed")
    else:
        print("[X API未設定] LINE通知のみ実行")
        append_to_log(f"{source}\t{date.today()}\tline_only")

    # LINE通知
    message = build_line_message(content, tweet_id, source)
    if send_line_message(message):
        print("[LINE通知完了]")
    else:
        # LINE未設定でも投稿内容をコンソールに出力
        print("\n=== 生成された投稿 ===")
        for i, t in enumerate(content["tweets"], 1):
            print(f"\n【案{i}】\n{t}")


if __name__ == "__main__":
    run()
