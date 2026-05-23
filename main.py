"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date, timedelta
from content_gen import PostCandidate, generate_posts_from_notes, generate_posts_from_rss

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

# Note記事を再利用するまでの日数
NOTE_REUSE_DAYS = 30


def load_posted_log() -> dict[str, date]:
    """ファイル名 -> 最終使用日 のマッピングを返す"""
    result: dict[str, date] = {}
    if not LOG_FILE.exists():
        return result
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            filename = parts[0]
            try:
                used_date = date.fromisoformat(parts[1])
                # 同一ファイルは最新日付で上書き
                if filename not in result or used_date > result[filename]:
                    result[filename] = used_date
            except ValueError:
                continue
    return result


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_eligible_notes(log: dict[str, date]) -> list[Path]:
    """NOTE_REUSE_DAYS 以上未使用のNote記事を返す"""
    if not NOTES_DIR.exists():
        return []
    today = date.today()
    eligible = []
    for p in NOTES_DIR.glob("*.md"):
        last_used = log.get(p.name)
        if last_used is None or (today - last_used) >= timedelta(days=NOTE_REUSE_DAYS):
            eligible.append(p)
    return eligible


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


def build_line_message(candidates: list[PostCandidate], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"\n🤖 今日({today})のX投稿案 [{source}]",
        "─" * 22,
    ]
    for i, c in enumerate(candidates[:3], 1):
        lines.append(f"\n【案{i}】\n{c.text}")
        if c.source_url:
            lines.append(f"🔗 {c.source_url}")
        if c.image_hint:
            lines.append(f"🖼 画像ヒント: {c.image_hint}")
        lines.append("─" * 22)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💡 リンクや画像も貼るとエンゲージメントUP")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    log = load_posted_log()
    eligible = get_eligible_notes(log)

    # Note記事から生成
    if eligible:
        note_file = random.choice(eligible)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # NOTE_URL が記事内に記載されている場合は取得
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split("NOTE_URL:", 1)[1].strip()
                break

        candidates = generate_posts_from_notes(note_text, feedback_text, note_url)
        if candidates:
            message = build_line_message(candidates, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成
    candidates = generate_posts_from_rss()
    if candidates:
        message = build_line_message(candidates, "AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
