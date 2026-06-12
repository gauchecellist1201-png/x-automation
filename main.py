"""
毎日21:00 JST にAI投稿案を生成してLINEに通知するスクリプト
"""

import os
import sys
import random
import requests
from pathlib import Path
from datetime import date
from content_gen import generate_posts_from_notes, generate_posts_from_rss, generate_thread_opener

LOG_FILE = Path("posted_log.txt")
NOTES_DIR = Path("data/notes")
FEEDBACK_FILE = Path("data/feedback.txt")
NOTE_REUSE_DAYS = 14  # 同じノートは14日後に再利用可能

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def load_posted_log() -> dict[str, date]:
    """ログを読み込み、ファイル名→最終投稿日のマッピングを返す"""
    result: dict[str, date] = {}
    if not LOG_FILE.exists():
        return result
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        filename = parts[0]
        try:
            posted_date = date.fromisoformat(parts[1])
            if filename not in result or posted_date > result[filename]:
                result[filename] = posted_date
        except ValueError:
            pass
    return result


def append_to_log(entry: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(entry + "\n")


def get_available_notes(posted_log: dict[str, date]) -> list[Path]:
    """未使用 or NOTE_REUSE_DAYS以上経過したノートファイルを返す"""
    if not NOTES_DIR.exists():
        return []
    today = date.today()
    available = []
    for p in NOTES_DIR.glob("*.md"):
        last_used = posted_log.get(p.name)
        if last_used is None or (today - last_used).days >= NOTE_REUSE_DAYS:
            available.append(p)
    return available


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


def build_line_message(posts: list[dict], source: str) -> str:
    """投稿案リストからLINE通知メッセージを生成"""
    today = date.today().strftime("%Y/%m/%d")
    lines = [
        f"🤖 今日({today})のX投稿案 [{source}]",
        "─" * 24,
    ]
    for i, post in enumerate(posts[:3], 1):
        post_type = "🧵スレッド案" if post.get("type") == "thread" else f"案{i}"
        lines.append(f"\n【{post_type}】\n{post['text']}")
        if post.get("image_prompt"):
            lines.append(f"📸 画像案: {post['image_prompt']}")
        lines.append("─" * 24)
    lines.append("\n✅ 気に入った案をコピーしてXに投稿！")
    lines.append("📝 feedback.txtに反応を記録するとAIが学習します")
    return "\n".join(lines)


def extract_note_url(note_text: str) -> str:
    """ノート本文からNOTE_URLを抽出"""
    for line in note_text.splitlines():
        if line.startswith("NOTE_URL:"):
            return line.replace("NOTE_URL:", "").strip()
    return ""


def main() -> None:
    line_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    line_user_id = os.environ["LINE_USER_ID"]

    posted_log = load_posted_log()
    available_notes = get_available_notes(posted_log)

    # 週1回スレッド起点ツイートを生成（月曜日）
    if date.today().weekday() == 0:
        thread_topics = [
            "AIエージェントがビジネスをどう変えるか",
            "医療AIの最前線と倫理的課題",
            "2026年のAI活用で差がつく経営判断",
            "生成AIで業務効率化に成功した企業の共通点",
        ]
        posts = generate_thread_opener(random.choice(thread_topics))
        if posts:
            message = build_line_message(posts, "🧵 スレッド案（月曜日特別）")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"thread\t{date.today()}\tline_notified")
                print("[LINE通知完了] スレッド案")
                return

    # 30%の確率でNote記事から生成（個人ブランディング）
    if available_notes and random.random() < 0.3:
        note_file = random.choice(available_notes)
        note_text = note_file.read_text(encoding="utf-8")
        feedback_text = FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else ""
        note_url = extract_note_url(note_text)
        posts = generate_posts_from_notes(note_text, feedback_text, note_url)
        if posts:
            message = build_line_message(posts, f"Note: {note_file.stem}")
            if send_line_message(line_token, line_user_id, message):
                append_to_log(f"{note_file.name}\t{date.today()}\tline_notified")
                print(f"[LINE通知完了] Note: {note_file.name}")
                return

    # メイン: RSSニュースから最新AI情報を元に投稿生成
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
