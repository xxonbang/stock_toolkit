"""미국 주식 관련 뉴스 수집 — Google News BUSINESS + Yahoo Finance Top News.

키워드 매칭 방식의 한계(특정 단어 포함 기사로만 한정 → 시그널 누락)를 피하기 위해
구글 뉴스 BUSINESS 토픽(무키워드 헤드라인) + 야후 파이낸스 톱 뉴스를 결합 수집.
"""
import html
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import feedparser
from bs4 import BeautifulSoup

from modules.news.collectors.base import CollectedItem

logger = logging.getLogger(__name__)

# 미국 비즈니스/시장 뉴스 RSS — 수집 다양성 확대 (2026-04-30)
US_RSS_SOURCES = [
    ("GoogleNews_BUSINESS", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
    ("YahooFinance",        "https://finance.yahoo.com/news/rssindex"),
    ("MarketWatch",         "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("CNBC_TopNews",        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"),
    ("InvestingCom",        "https://www.investing.com/rss/news.rss"),
    ("MarketWatch_Markets", "https://feeds.marketwatch.com/marketwatch/marketpulse/"),
]


def _fetch_feed(url: str):
    """feedparser 호출 (테스트에서 mock 가능)"""
    return feedparser.parse(url)


def _clean_html(html: str) -> str:
    """RSS body의 HTML 태그/엔티티 제거 → 순수 텍스트."""
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def _entry_to_item(entry, source: str = "") -> Optional[CollectedItem]:
    if not getattr(entry, "title", None) or not getattr(entry, "link", None):
        return None
    pub = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not pub:
        return None
    published = datetime(*pub[:6], tzinfo=timezone.utc)
    body_raw = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    body = _clean_html(body_raw)[:500]
    # 출처를 body 끝에 추가 (LLM이 출처 인지하도록)
    if source and source not in body:
        body = (body + f" ({source})").strip()
    return CollectedItem(
        batch="us_news", idx=0,
        title=html.unescape(entry.title.strip()),
        body=body,
        url=entry.link,
        published_at=published,
    )


def collect(now: Optional[datetime] = None, limit: int = 50) -> List[CollectedItem]:
    """36시간 이내 미국 비즈니스/금융 뉴스를 6개 소스에서 수집, 중복 제거 후 limit개."""
    import time as _time
    if now is None:
        now = datetime.now(timezone.utc)
    since = now - timedelta(hours=36)

    seen_urls = set()
    items: List[CollectedItem] = []

    for source_name, url in US_RSS_SOURCES:
        t_start = _time.time()
        try:
            feed = _fetch_feed(url)
        except Exception as e:
            logger.warning(f"us_news fetch 실패 ({source_name}, {_time.time()-t_start:.2f}s): {e}")
            continue
        raw_count = len(getattr(feed, "entries", []))
        before = len(items)
        for entry in getattr(feed, "entries", []):
            it = _entry_to_item(entry, source=source_name)
            if not it:
                continue
            if it.published_at < since:
                continue
            if it.url in seen_urls:
                continue
            seen_urls.add(it.url)
            items.append(it)
        logger.info(
            f"  {source_name}: raw={raw_count}건 → 36h+중복제거 후 +{len(items) - before}개 "
            f"({_time.time()-t_start:.2f}s)"
        )

    # 정렬: (1) 6h 이내 최신 우선, (2) 본문 200자 이상 우선, (3) 발행시각 최신
    six_hours_ago = now - timedelta(hours=6)
    items.sort(
        key=lambda x: (x.published_at >= six_hours_ago, len(x.body) >= 200, x.published_at),
        reverse=True,
    )
    items = items[:limit]
    for i, it in enumerate(items, start=1):
        it.idx = i
    logger.info(f"us_news 수집 완료: {len(items)}개 ({len(US_RSS_SOURCES)}개 소스)")
    return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for it in collect():
        print(f"[#{it.idx}] {it.title}")
