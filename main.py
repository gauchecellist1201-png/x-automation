"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date, timedelta
from content_gen import (
    generate_posts_from_notes,
    generate_posts_from_rss,
    suggest_image,
    _generate_original_ai_insight,
)

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

NOTE_COOLDOWN_DAYS = 7  # 同じノートを再利用するまでの待機日数


def load_recently_used_notes(days: int = NOTE_COOLDOWN_DAYS) -> set[str]:
    """直近N日以内に使用したノートファイル名を返す"""
    if not LOG_FILE.exists():
        return set()
    cutoff = date.today() - timedelta(days=days)
    recent: set[str] = set()
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            filename, post_date_str = parts[0], parts[1]
            try:
                if date.fromisoformat(post_date_str) >= cutoff:
                    recent.add(filename)
            except ValueError:
                pass
    return recent


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_available_notes() -> list[Path]:
    """クールダウン期間を過ぎたノートファイルを返す"""
    if not NOTES_DIR.exists():
        return []
    recently_used = load_recently_used_notes()
    return [p for p in NOTES_DIR.glob("*.md") if p.name not in recently_used]


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


def build_line_message(posts: list[str], source: str, selected_news: str = "") -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🤖 今日({today})のX投稿案",
        f"📰 ソース: {selected_news or source}",
        "─" * 22,
    ]
    viral_types = ["数字インパクト", "逆張り・反常識", "FOMO（競合脅威）", "問いかけ", "最新情報＋解説"]
    for i, post in enumerate(posts, 1):
        vtype = viral_types[i - 1] if i <= len(viral_types) else f"案{i}"
        image_hint = suggest_image(post)
        lines.append(f"\n【案{i} — {vtype}】\n{post}")
        lines.append(f"🖼 画像ヒント: {image_hint}")
        lines.append("─" * 22)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💡 画像を添付するとエンゲージメント+30〜50%向上します")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    available_notes = get_available_notes()

    # ノートから生成（週1〜2回程度、クールダウン管理）
    if available_notes and random.random() < 0.35:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        posts = generate_posts_from_notes(note_text, feedback_text)
        if posts:
            message = build_line_message(posts, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成（メインルート）
    posts, selected_news = generate_posts_from_rss()
    if posts:
        message = build_line_message(posts, "AIニュース", selected_news)
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print(f"[LINE通知完了] RSSニュース: {selected_news}")
            return

    # フォールバック：オリジナル洞察
    posts, label = _generate_original_ai_insight()
    if posts:
        message = build_line_message(posts, label)
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"original\t{date.today()}\tline_notified")
            print("[LINE通知完了] オリジナル洞察")
            return

    print("投稿候補を生成できませんでした。")
    sys.exit(1)


if __name__ == "__main__":
    main()
