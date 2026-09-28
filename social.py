"""Free, review-first CORE social drafts and LINE delivery."""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib import request
from urllib.error import HTTPError
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
LINE_URL = "https://api.line.me/v2/bot/message/push"
FEED = "https://news.google.com/rss/search?q=AI+企業+業務&hl=ja&gl=JP&ceid=JP:ja"

# Public, reusable ideas only. Customer names, unreleased work and internal numbers stay out.
IDEAS = [
    ("営業", "商談後のメモが担当者の頭の中だけに残る", "会話の要点、次の約束、提案期限を同じ形式で記録する"),
    ("見積", "見積のたびに過去案件を一から探す", "過去の見積を条件別に検索し、根拠を確認できる下書きを作る"),
    ("採用", "面接の評価が人によってばらつく", "職務要件を先に言語化し、同じ項目で記録する"),
    ("顧客対応", "同じ質問への回答を毎回作り直す", "承認済みの回答を整理し、参照元付きの返信案を作る"),
    ("経理", "領収書の確認が月末に集中する", "日々の分類案を作り、例外だけ人が確認する"),
    ("議事録", "会議のあと担当と期限が曖昧になる", "決定事項、担当者、期限の3点を必ず残す"),
    ("社内知識", "10年分の資料があるのに誰も探せない", "アクセス権を整理してから検索対象を絞る"),
    ("意思決定", "数字はあるのに次の一手が決まらない", "指標の定義、変化、仮説を一枚にまとめる"),
    ("現場", "紙の報告が事務所に戻るまで見えない", "入力を現場で一度にし、確認が必要なものだけ通知する"),
    ("AI導入", "ツールを配っただけで業務が変わらない", "一つの業務の入力、判断、承認まで描き直す"),
    ("品質", "AIの回答がもっともらしくても根拠が追えない", "参照元を示し、公開前に人が確認する"),
    ("時間", "浮いた時間の使い道が決まっていない", "短縮した時間を顧客との対話や創造に振り向ける"),
]


def daily_posts(day):
    """Three distinct X drafts, deliberately short enough for a free account."""
    offset = (day - day.replace(month=1, day=1)).days
    result = []
    for position, index in enumerate((offset, offset + 4, offset + 8), 1):
        area, pain, action = IDEAS[index % len(IDEAS)]
        if position == 1:
            post = f"{area}のAI活用は、まず『{pain}』から考える。{action}。小さな業務を一つ変えると、次に変える場所も見えてきます。"
        elif position == 2:
            post = f"経営者に聞きたいこと。{area}で『{pain}』と感じていませんか。まずは{action}。ここまで具体化して初めて、AIが役に立ちます。"
        else:
            post = f"AIで減らしたいのは、人の価値ではなく無駄な手間。{area}なら、{pain}状態を見直し、{action}。空いた時間を、人にしかできない仕事へ。"
        assert len(post) <= 280
        result.append(post)
    return result


def recent_headlines(now, limit=3):
    """Headlines are references to verify, never rewritten as asserted facts."""
    try:
        req = request.Request(FEED, headers={"User-Agent": "CORE-Social-OS/1.0"})
        with request.urlopen(req, timeout=10) as response:
            root = ElementTree.fromstring(response.read(500_000))
        items = []
        for item in root.findall("./channel/item"):
            title, link, pub = (item.findtext(tag, "").strip() for tag in ("title", "link", "pubDate"))
            if not (title and link and pub and link.startswith("https://")):
                continue
            published = parsedate_to_datetime(pub)
            if now - timedelta(days=7) <= published <= now + timedelta(hours=1):
                items.append((title[:100], link))
            if len(items) >= limit:
                break
        return items
    except (OSError, ValueError, ElementTree.ParseError, TimeoutError):
        return []


def weekly_draft(now, headlines):
    lines = ["【経営者のためのAI実践室｜今週の投稿案】", "今週の実務テーマ：AIを使う前に、業務を一つ選ぶ。", "", "① 繰り返し起きる作業を一つ書き出す", "② 入力と最終判断を誰が担うか決める", "③ 1週間試し、時間と品質の変化を見る", "", "AI導入は、ツール選びより業務の設計から。皆さんの会社で最初に見直したい仕事は何ですか？"]
    if headlines:
        lines += ["", "参考記事（見出しを確認してから投稿してください）:"]
        lines += [f"・{title}\n{link}" for title, link in headlines]
    return "\n".join(lines)


def push(messages, token, user_id, retry_key):
    if not token or not user_id:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN and LINE_USER_ID are required")
    if not 1 <= len(messages) <= 5 or any(len(m) > 5000 for m in messages):
        raise ValueError("LINE message limit exceeded")
    payload = json.dumps({"to": user_id, "messages": [{"type": "text", "text": m} for m in messages]}, ensure_ascii=False).encode()
    req = request.Request(LINE_URL, data=payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "X-Line-Retry-Key": str(uuid.uuid5(uuid.NAMESPACE_URL, retry_key))}, method="POST")
    try:
        with request.urlopen(req, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError(f"LINE rejected push: HTTP {response.status}")
    except HTTPError as error:
        if error.code != 409:  # LINE has already accepted this retry key.
            raise


def main(kind=None, now=None):
    now = now or datetime.now(JST)
    day = now.date()
    kind = kind or os.getenv("DRAFT_KIND", "daily")
    if kind == "daily":
        messages = [f"【{day}｜X投稿案 {i}/3】\n{post}\n\n確認してからXへコピーしてください。" for i, post in enumerate(daily_posts(day), 1)]
    elif kind == "weekly":
        messages = [weekly_draft(now.astimezone(timezone.utc), recent_headlines(now.astimezone(timezone.utc)))]
    else:
        raise ValueError(f"Unknown draft kind: {kind}")
    push(messages, os.getenv("LINE_CHANNEL_ACCESS_TOKEN"), os.getenv("LINE_USER_ID"), f"core-social:{kind}:{day}")
    print(f"LINE delivered: {kind} {day}")


if __name__ == "__main__":
    main()
