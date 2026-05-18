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

FORMAT_LABELS = {
    "A": "📊 統計ショック型",
    "B": "❓ 問いかけ型",
    "C": "📋 リスト型（保存推奨）",
    "D": "⚡ 逆張り型",
    "E": "🔄 Before/After型",
    "F": "🔮 予言・未来型",
}


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
    all_notes = list(NOTES_DIR.glob("*.md"))
    # 当日まだ使っていないものを優先、なければ全部から選ぶ
    today_str = str(date.today())
    used_today = {l.split("\t")[0] for l in posted if today_str in l}
    unposted = [p for p in all_notes if p.name not in used_today]
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


def _detect_format(post: str) -> str:
    """投稿文からフォーマット種別を推定してラベルを返す"""
    if any(c in post for c in ["①", "②", "③", "1.", "2.", "3."]) and "\n" in post:
        return FORMAT_LABELS["C"]
    if "Before" in post or "After" in post or "→" in post:
        return FORMAT_LABELS["E"]
    if "%" in post or "円" in post or any(c.isdigit() for c in post[:20]):
        return FORMAT_LABELS["A"]
    if post.rstrip().endswith(("？", "?", "か", "か。")):
        return FORMAT_LABELS["B"]
    if any(w in post for w in ["逆", "実は", "間違", "本当は", "勘違"]):
        return FORMAT_LABELS["D"]
    if any(w in post for w in ["年後", "将来", "未来", "淘汰", "なくなる"]):
        return FORMAT_LABELS["F"]
    return "💡 インサイト型"


def build_line_message(posts: list[str], source: str) -> str:
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🤖 今日({today})のX投稿案",
        f"📡 ソース: {source}",
        "━" * 18,
    ]
    for i, post in enumerate(posts[:3], 1):
        fmt = _detect_format(post)
        lines.append(f"\n【案{i}】{fmt}")
        lines.append(post)
        lines.append("━" * 18)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿してください！")
    lines.append("💬 反応が良かったものは data/feedback.txt に追記してください")
    return "\n".join(lines)


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted = load_posted_log()
    unposted = get_unposted_notes(posted)

    # Note記事から生成（優先）
    if unposted:
        note_file = random.choice(unposted)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""

        # NOTE_URL があればプロンプトに渡す
        note_url = ""
        for line in note_text.splitlines():
            if line.startswith("NOTE_URL:"):
                note_url = line.split("NOTE_URL:", 1)[1].strip()
                break

        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            message = build_line_message(posts, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # RSSニュースから生成（フォールバック）
    posts = generate_posts_from_rss()
    if posts:
        message = build_line_message(posts, "最新AIニュース")
        if send_line_message(line_token, line_user_id, message):
            append_to_log(f"rss\t{date.today()}\tline_notified")
            print("[LINE通知完了] RSSニュース")
            return

    print("投稿候補がありませんでした。")
    sys.exit(0)


if __name__ == "__main__":
    main()
