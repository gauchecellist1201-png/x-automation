"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
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


def load_posted_log() -> set[str]:
    """ログからファイル名のみを抽出して返す（タブ区切りの1列目）"""
    if not LOG_FILE.exists():
        return set()
    names = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if parts and parts[0].strip():
            names.add(parts[0].strip())
    return names


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
    # LINEは1メッセージ5000文字制限があるため分割
    chunks = _split_message(message, limit=4800)
    success = True
    for chunk in chunks:
        payload = {
            "to": user_id,
            "messages": [{"type": "text", "text": chunk}],
        }
        response = requests.post(LINE_PUSH_URL, headers=headers, json=payload)
        if response.status_code != 200:
            success = False
    return success


def _split_message(text: str, limit: int = 4800) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


def build_line_message(singles: list[str], thread: list[str], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 22,
    ]

    # 単発ツイート案
    if singles:
        lines.append("\n【単発ツイート案】（そのままコピー可）")
        for i, post in enumerate(singles[:3], 1):
            char_count = len(post)
            lines.append(f"\n▶ 案{i}（{char_count}文字）\n{post}")
            lines.append("─" * 22)

    # スレッド案
    if thread:
        lines.append("\n【スレッド案】（Xで連続投稿 → 高エンゲージメント）")
        lines.append("━" * 22)
        for i, tweet in enumerate(thread, 1):
            lines.append(f"\n{i}/ {tweet}")
        lines.append("\n" + "━" * 22)
        lines.append("💡 画像を添付すると更にリーチUP（1ツイート目推奨）")

    lines.append("\n✅ 気に入った案をコピーしてXに投稿！")
    lines.append("📌 投稿後に反応が良かったものをfeedback.txtに追加してください")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # Note記事から生成（未投稿のものがある場合）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # Note内のURL抽出
        note_url = ""
        for line in note_text.splitlines():
            if line.strip().startswith("NOTE_URL:"):
                note_url = line.split(":", 1)[1].strip()
                break

        singles = generate_posts_from_notes(note_text, feedback_text, note_url)

        # Note記事でもスレッドを生成（RSS使用）
        from content_gen import fetch_rss_headlines, generate_thread_from_rss, _generate_original_thread
        headlines = fetch_rss_headlines()
        thread = generate_thread_from_rss(headlines) if headlines else _generate_original_thread()

        if singles or thread:
            message = build_line_message(singles, thread, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    singles, thread = generate_posts_from_rss()
    if singles or thread:
        message = build_line_message(singles, thread, "AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
