"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
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
    generate_thread_from_notes,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_note_names() -> set[str]:
    """ログからノートファイル名のみを抽出（重複使用を防ぐ）"""
    if not LOG_FILE.exists():
        return set()
    names: set[str] = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if parts and parts[0].endswith(".md"):
            names.add(parts[0])
    return names


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_unposted_notes(posted_names: set[str]) -> list[Path]:
    """まだ使っていないノートファイルを返す。全部使い切ったらリセット。"""
    if not NOTES_DIR.exists():
        return []
    all_notes = list(NOTES_DIR.glob("*.md"))
    unposted = [p for p in all_notes if p.name not in posted_names]
    # 全ノートを使い切ったらすべてをリセットして再利用
    return unposted if unposted else all_notes


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


def build_line_message(posts: list[str], source: str, is_thread: bool = False) -> str:
    today = date.today().strftime("%Y/%m/%d")
    format_label = "スレッド" if is_thread else "単独ツイート"
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source} / {format_label}]",
        "─" * 20,
    ]
    for i, post in enumerate(posts[:5] if is_thread else posts[:3], 1):
        label = f"【{i}/{len(posts[:5])}】" if is_thread else f"【案{i}】"
        lines.append(f"\n{label}\n{post}")
        lines.append("─" * 20)
    if is_thread:
        lines.append("\n✅ 上記をスレッドで投稿するとフォロワー増加に効果的です！")
    else:
        lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    return "\n".join(lines)


def extract_note_url(note_text: str) -> str:
    """NOTE_URL: の行からURLを取得"""
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.split("NOTE_URL:", 1)[1].strip()
    return ""


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted_names = load_posted_note_names()
    note_candidates = get_unposted_notes(posted_names)

    if note_candidates:
        note_file = random.choice(note_candidates)
        note_text = note_file.read_text(encoding="utf-8")
        note_url = extract_note_url(note_text)
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # 確率でスレッド形式 or 単独ツイートを選択（スレッドは週2回程度）
        use_thread = random.random() < 0.3
        if use_thread:
            posts = generate_thread_from_notes(note_text)
        else:
            posts = generate_posts_from_notes(note_text, feedback_text, note_url)

        if posts:
            message = build_line_message(posts, f"Note: {note_file.stem}", is_thread=use_thread)
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                format_label = "スレッド" if use_thread else "単独"
                print(f"[LINE通知完了] Note: {note_file.name} ({format_label})")
                return

    # RSSニュースから生成
    posts = generate_posts_from_rss()
    if posts:
        message = build_line_message(posts, "AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
