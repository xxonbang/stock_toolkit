"""한국 주식 관련 뉴스 수집 — Google News BUSINESS (ko) + 네이버 금융 메인뉴스.

키워드 매칭 한계 회피를 위해 구글 뉴스 BUSINESS 토픽(무키워드) + 네이버 금융
메인뉴스 크롤링을 결합 수집.
"""
import html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as _requests
    _IMPERSONATE_KWARGS = {"impersonate": "chrome120"}
except ImportError:
    import requests as _requests
    _IMPERSONATE_KWARGS = {}

from modules.news.collectors.base import CollectedItem

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 한국 비즈니스/시장 뉴스 RSS (2026-04-30 검증: 11개 매체 통합)
# 작동 안 하는 한경 구 RSS / 이데일리 / 머니투데이 등은 제외, 매경/연합 다중 카테고리 추가.
KR_RSS_SOURCES = [
    ("GoogleNews_BUSINESS_KR", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"),
    ("Hankyung_All",           "https://www.hankyung.com/feed"),  # 신 URL
    # 매일경제 (5개 카테고리, 50건씩)
    ("Maeil_Economy",          "https://www.mk.co.kr/rss/30000001/"),
    ("Maeil_Enterprise",       "https://www.mk.co.kr/rss/40300001/"),
    ("Maeil_Finance",          "https://www.mk.co.kr/rss/50300009/"),
    ("Maeil_GlobalEconomy",    "https://www.mk.co.kr/rss/30100041/"),
    ("Maeil_Stock",            "https://www.mk.co.kr/rss/30000023/"),
    # 연합뉴스 (4개 카테고리, 120건씩 — 가장 다양한 시그널)
    ("Yonhap_TopNews",         "https://www.yna.co.kr/rss/news.xml"),
    ("Yonhap_Economy",         "https://www.yna.co.kr/rss/economy.xml"),
    ("Yonhap_Industry",        "https://www.yna.co.kr/rss/industry.xml"),
    ("Yonhap_Market",          "https://www.yna.co.kr/rss/market.xml"),
]
# 네이버 금융 메인뉴스 (HTML 크롤링, 공식 RSS 없음 — 별도 처리)
NAVER_FINANCE_MAIN = "https://finance.naver.com/news/mainnews.naver"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://finance.naver.com/",
}

_NAVER_DT_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\s+(\d{1,2}):(\d{2})")


def _fetch_feed(url: str):
    return feedparser.parse(url)


def _fetch_html(url: str) -> str:
    resp = _requests.get(url, headers=HEADERS, timeout=15, **_IMPERSONATE_KWARGS)
    resp.raise_for_status()
    return resp.text


def _clean_html(html: str) -> str:
    """RSS body의 HTML 태그/엔티티 제거 → 순수 텍스트."""
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def _entry_to_item(entry, source: str = "") -> Optional[CollectedItem]:
    """RSS entry → CollectedItem. source는 body 끝에 표기."""
    if not getattr(entry, "title", None) or not getattr(entry, "link", None):
        return None
    pub = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not pub:
        return None
    published = datetime(*pub[:6], tzinfo=timezone.utc)
    body_raw = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    body = _clean_html(body_raw)[:500]
    if source and source not in body:
        body = (body + f" ({source})").strip()
    return CollectedItem(
        batch="kr_news", idx=0,
        title=html.unescape(entry.title.strip()), body=body,
        url=entry.link, published_at=published,
    )


def _parse_naver_finance(html: str, now_kst: datetime) -> List[CollectedItem]:
    """네이버 금융 메인뉴스 HTML 파싱."""
    soup = BeautifulSoup(html, "html.parser")
    items: List[CollectedItem] = []
    # 셀렉터 후보 (페이지 구조 변동 대응)
    rows = soup.select(".mainNewsList li") or soup.select("ul.newsList li") or soup.select("li.block1")
    for li in rows:
        a = li.select_one("dd.articleSubject a") or li.select_one(".articleSubject a") or li.select_one("a")
        if not a:
            continue
        title = (a.get("title") or a.get_text(strip=True) or "").strip()
        href = a.get("href", "")
        if not title or len(title) < 5 or not href:
            continue
        url = urljoin("https://finance.naver.com", href)
        # 본문 요약
        summary_el = li.select_one("dd.articleSummary") or li.select_one(".articleSummary")
        body = ""
        if summary_el:
            # 시간 태그(.wdate) 제외하고 본문만
            for tag in summary_el.select(".wdate, .press"):
                tag.extract()
            body = summary_el.get_text(separator=" ", strip=True)[:500]
        # 발행 시간
        time_el = li.select_one(".wdate") or li.select_one(".date")
        published = now_kst
        if time_el:
            m = _NAVER_DT_RE.search(time_el.get_text(strip=True))
            if m:
                y, mo, d, h, mi = map(int, m.groups())
                try:
                    published = datetime(y, mo, d, h, mi, tzinfo=KST)
                except ValueError:
                    pass
        items.append(CollectedItem(
            batch="kr_news", idx=0,
            title=title, body=body,
            url=url, published_at=published,
        ))
    return items


def collect(now: Optional[datetime] = None, limit: int = 50) -> List[CollectedItem]:
    """36시간 이내 한국 비즈니스/금융 뉴스를 다중 소스에서 수집, 중복 제거 후 limit개."""
    import time as _time
    if now is None:
        now = datetime.now(timezone.utc)
    since = now - timedelta(hours=36)
    now_kst = now.astimezone(KST)

    seen_urls = set()
    items: List[CollectedItem] = []

    # 1. RSS 소스들 (Google News + 한국경제 + 매일경제 + 이데일리)
    for source_name, url in KR_RSS_SOURCES:
        t0 = _time.time()
        try:
            feed = _fetch_feed(url)
            raw_count = len(getattr(feed, "entries", []))
            before = len(items)
            for entry in getattr(feed, "entries", []):
                it = _entry_to_item(entry, source=source_name)
                if not it or it.published_at < since or it.url in seen_urls:
                    continue
                seen_urls.add(it.url)
                items.append(it)
            logger.info(f"  {source_name}: raw={raw_count} → +{len(items) - before}개 ({_time.time()-t0:.2f}s)")
        except Exception as e:
            logger.warning(f"kr_news fetch 실패 ({source_name}, {_time.time()-t0:.2f}s): {e}")

    # 2. 네이버 금융 메인뉴스 (HTML 크롤링)
    t0 = _time.time()
    try:
        html_text = _fetch_html(NAVER_FINANCE_MAIN)
        before = len(items)
        parsed = _parse_naver_finance(html_text, now_kst)
        for it in parsed:
            if it.published_at < since or it.url in seen_urls:
                continue
            seen_urls.add(it.url)
            items.append(it)
        logger.info(
            f"  Naver_Finance_Main: HTML {len(html_text):,}자 → 파싱 {len(parsed)}건 → "
            f"+{len(items) - before}개 ({_time.time()-t0:.2f}s)"
        )
    except Exception as e:
        logger.warning(f"kr_news fetch 실패 (Naver_Finance_Main, {_time.time()-t0:.2f}s): {e}")

    # 정렬: 6h 내 최신 우선, 본문 200+ 우선, 발행시각 최신
    six_hours_ago = now - timedelta(hours=6)
    items.sort(
        key=lambda x: (x.published_at >= six_hours_ago, len(x.body) >= 200, x.published_at),
        reverse=True,
    )
    items = items[:limit]
    for i, it in enumerate(items, start=1):
        it.idx = i
    logger.info(f"kr_news 수집 완료: {len(items)}개 ({len(KR_RSS_SOURCES)}개 RSS + 네이버 금융)")
    return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for it in collect():
        print(f"[#{it.idx}] {it.title}")
