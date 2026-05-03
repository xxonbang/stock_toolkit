"""3단계 LLM 분석 — extract → top3 → outlook (+ youtube TOP3).

trade_info_sender의 trend_extractor.py를 stock_toolkit 경로에 맞춰 이식.
- 별칭 정규화, 인덱스/시장명 필터, 최소 빈도 임계값 적용
- enable_search=True (outlook): Gemini Google Search grounding으로 1주일 전망 작성
"""
from __future__ import annotations

import json
import logging
import re
from datetime import timedelta, timezone
from pathlib import Path
from typing import Dict, List

from modules.news.collectors.base import CollectedItem, format_indexed_text

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"

LABEL_TO_BATCH = {
    "미뉴스": "us_news",
    "한뉴스": "kr_news",
}
BUNDLE_PATTERN = re.compile(r"\[(미뉴스|한뉴스)((?:#\d+,?)+)\]")
NUM_PATTERN = re.compile(r"#(\d+)")


def verify_indices(text: str, batches: Dict[str, List[CollectedItem]]) -> Dict:
    """LLM 출력의 [라벨#N] 인덱스가 실제 수집 데이터에 존재하는지 검증."""
    cited = set()
    for label, body in BUNDLE_PATTERN.findall(text):
        for n in NUM_PATTERN.findall(body):
            cited.add((LABEL_TO_BATCH[label], int(n)))
    actual = {(b, item.idx) for b, items in batches.items() for item in items}
    missing = sorted(cited - actual)
    return {"ok": len(missing) == 0, "missing": missing, "total_refs": len(cited)}


def _load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _strip_codeblock(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


_AI_ERROR_SENTINELS = ("API 할당량 초과", "오류:")


class AIUpstreamError(RuntimeError):
    """Gemini 외부 장애 — JSON 파싱 재시도 무의미"""


def _parse_json_with_retry(
    client,
    prompt: str,
    max_retries: int = 3,
    temperature: float = 0.2,
    enable_search: bool = False,
    max_output_tokens: int = 32000,
):
    last_err = None
    for attempt in range(max_retries):
        attempt_prompt = prompt
        if attempt > 0:
            attempt_prompt = (
                prompt
                + "\n\n[중요] 이전 응답이 JSON 파싱에 실패했습니다. "
                "반드시 유효한 JSON 객체만 출력하고 마크다운/설명 텍스트 금지."
            )
        text, _usage = client.call(
            prompt=attempt_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            enable_search=enable_search,
        )
        stripped = (text or "").strip()
        for sentinel in _AI_ERROR_SENTINELS:
            if stripped.startswith(sentinel):
                raise AIUpstreamError(stripped[:300])
        try:
            cleaned = _strip_codeblock(text)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            last_err = e
            logger.warning(
                f"JSON 파싱 실패 (시도 {attempt + 1}/{max_retries}): {e} | "
                f"응답 길이 {len(text)}자, 앞 200자: {text[:200]!r}"
            )
    raise RuntimeError(f"JSON 파싱 {max_retries}회 실패: {last_err}")


# 별칭 정규화 (trade_info_sender와 동일)
_NAME_ALIASES: Dict[str, str] = {
    "엔비디아": "Nvidia", "NVDA": "Nvidia", "nvidia corp": "Nvidia", "NVIDIA": "Nvidia",
    "애플": "Apple", "AAPL": "Apple",
    "마이크로소프트": "Microsoft", "MSFT": "Microsoft", "MS": "Microsoft",
    "알파벳": "Alphabet", "GOOGL": "Alphabet", "GOOG": "Alphabet", "구글": "Alphabet", "Google": "Alphabet",
    "아마존": "Amazon", "AMZN": "Amazon",
    "메타": "Meta", "META": "Meta", "Facebook": "Meta", "페이스북": "Meta",
    "테슬라": "Tesla", "TSLA": "Tesla",
    "AMD": "AMD", "에이엠디": "AMD",
    "TSMC": "TSMC", "타이완 반도체": "TSMC", "Taiwan Semiconductor": "TSMC",
    "인텔": "Intel", "INTC": "Intel",
    "브로드컴": "Broadcom", "AVGO": "Broadcom",
    "팔란티어": "Palantir", "PLTR": "Palantir",
    "삼성전자우": "삼성전자", "005930": "삼성전자",
    "SK하이닉스": "SK하이닉스", "000660": "SK하이닉스", "하이닉스": "SK하이닉스",
    "LG에너지솔루션": "LG에너지솔루션", "LG엔솔": "LG에너지솔루션", "엘지에너지솔루션": "LG에너지솔루션",
    "현대차": "현대자동차", "현대자동차": "현대자동차",
    "네이버": "NAVER", "Naver": "NAVER",
    "카카오": "Kakao", "KAKAO": "Kakao",
    "셀트리온": "셀트리온",
    "한화에어로스페이스": "한화에어로스페이스", "한화에어로": "한화에어로스페이스",
    "AI": "AI", "인공지능": "AI", "artificial intelligence": "AI", "Artificial Intelligence": "AI",
    "반도체": "반도체", "semiconductor": "반도체", "Semiconductor": "반도체", "Semiconductors": "반도체",
    "2차전지": "2차전지", "이차전지": "2차전지", "Battery": "2차전지", "EV battery": "2차전지",
    "바이오": "바이오", "biotech": "바이오", "Biotech": "바이오", "제약": "바이오", "Pharmaceuticals": "바이오",
    "방산": "방산", "Defense": "방산", "Defence": "방산",
    "원자력": "원자력", "Nuclear": "원자력", "원전": "원자력",
    "Cloud": "클라우드", "클라우드": "클라우드",
    "Fintech": "핀테크", "핀테크": "핀테크",
    "Healthcare": "Healthcare", "헬스케어": "Healthcare",
    "Energy": "Energy", "에너지": "Energy",
}


def _canonical_name(name: str) -> str:
    if not name:
        return name
    return _NAME_ALIASES.get(name.strip(), name.strip())


def _normalize_aliases_in_extraction(extraction: Dict) -> Dict:
    for batch_key in ("us_news", "kr_news"):
        batch = extraction.get(batch_key)
        if not isinstance(batch, dict):
            continue
        for field in ("stocks", "sectors"):
            entries = batch.get(field, [])
            merged: Dict[str, Dict] = {}
            for e in entries:
                canon = _canonical_name(e.get("name", ""))
                if not canon:
                    continue
                if canon not in merged:
                    merged[canon] = {"name": canon, "freq": 0, "refs": []}
                merged[canon]["freq"] += e.get("freq", 0)
                merged[canon]["refs"].extend(e.get("refs", []) or [])
            for v in merged.values():
                v["refs"] = sorted(set(v["refs"]))
            batch[field] = sorted(merged.values(), key=lambda x: x["freq"], reverse=True)
    return extraction


_INDEX_TOKENS = {
    "코스피", "코스닥", "kospi", "kospi200", "kospi 200", "코스피200",
    "kosdaq", "krx", "k200", "k-otc", "한국 증시", "한국증시",
    "s&p 500", "s&p500", "s&p", "snp500",
    "nasdaq", "nasdaq composite", "nasdaq-100", "nasdaq 100",
    "dow", "dow jones", "djia", "dow industrial",
    "russell", "russell 2000", "russell 1000",
    "vix", "wall street", "월스트리트", "미국 증시", "미국증시",
    "spy", "qqq", "arkk", "vti", "voo", "iwm", "tqqq", "sqqq", "soxl", "soxs",
}


def _is_index_or_market(name: str) -> bool:
    if not name:
        return False
    n = name.strip().lower()
    for token in _INDEX_TOKENS:
        if n == token or token in n.split():
            return True
        if " " in token and token in n:
            return True
    return False


def _filter_indices_from_extraction(extraction: Dict) -> Dict:
    for batch_key in ("us_news", "kr_news"):
        batch = extraction.get(batch_key)
        if not isinstance(batch, dict):
            continue
        for field in ("stocks", "sectors"):
            entries = batch.get(field, [])
            filtered = [e for e in entries if not _is_index_or_market(e.get("name", ""))]
            removed = len(entries) - len(filtered)
            if removed:
                logger.info(f"  필터: {batch_key}.{field}에서 인덱스 {removed}건 제거")
            batch[field] = filtered
    return extraction


def _filter_indices_from_top3(top3: Dict) -> Dict:
    for key in ("us_top3_sectors", "us_top3_stocks", "kr_top3_sectors", "kr_top3_stocks"):
        entries = top3.get(key, [])
        filtered = [e for e in entries if not _is_index_or_market(e.get("name", ""))]
        removed = len(entries) - len(filtered)
        if removed:
            logger.info(f"  필터: {key}에서 인덱스 {removed}건 제거")
        top3[key] = filtered
    return top3


# 영역별 임계값 — 한국은 매체 다양성으로 시그널 분산되어 더 낮게 설정 (2026-04-30)
# 미국 50건의 10%/16%, 한국 다중매체 50건의 8%/12%
MIN_STOCK_FREQ_US = 5
MIN_SECTOR_FREQ_US = 8
MIN_STOCK_FREQ_KR = 4
MIN_SECTOR_FREQ_KR = 6
# 임계값 미달이어도 노이즈가 아닌 최소선 — UI에 "약한 시그널" 라벨로 노출
MIN_VISIBLE_FREQ_STOCK = 2
MIN_VISIBLE_FREQ_SECTOR = 3


def _entry_total_freq(entry: Dict, region: str) -> int:
    if region == "us":
        return len(entry.get("us_news_refs", []) or [])
    return len(entry.get("kr_news_refs", []) or [])


def _enforce_min_freq_top3(top3: Dict) -> Dict:
    """임계값 미달 entry는 _weak_signal=True 마킹하여 보존 (UI에서 약한 시그널 라벨).
    완전 잡음(VISIBLE 미만)만 제외.
    """
    region_thresh = {
        "us": (MIN_STOCK_FREQ_US, MIN_SECTOR_FREQ_US),
        "kr": (MIN_STOCK_FREQ_KR, MIN_SECTOR_FREQ_KR),
    }
    for region, (min_stock, min_sector) in region_thresh.items():
        for kind, min_strong, min_visible in [
            ("stocks",  min_stock,  MIN_VISIBLE_FREQ_STOCK),
            ("sectors", min_sector, MIN_VISIBLE_FREQ_SECTOR),
        ]:
            key = f"{region}_top3_{kind}"
            entries = top3.get(key, [])
            kept, weak, dropped = [], 0, 0
            for e in entries:
                f = _entry_total_freq(e, region)
                if f >= min_strong:
                    kept.append(e)
                elif f >= min_visible:
                    e["_weak_signal"] = True
                    kept.append(e)
                    weak += 1
                else:
                    dropped += 1
            if dropped:
                logger.info(f"  필터: {key} 잡음 {dropped}건 제거 (<{min_visible}건)")
            if weak:
                logger.info(f"  약한 시그널: {key} {weak}건 (낮은 빈도지만 보존)")
            top3[key] = kept
    return top3


def extract_per_batch(batches: Dict[str, List[CollectedItem]], client) -> Dict:
    """AI 콜 #1 — 2배치(미뉴스/한뉴스)에서 종목/섹터 각 10개씩 추출."""
    template = _load_prompt("trend_extract.txt")
    all_items: List[CollectedItem] = []
    for b in ("us_news", "kr_news"):
        all_items.extend(batches.get(b, []))
    collected_text = format_indexed_text(all_items)
    prompt = template.replace("{COLLECTED_TEXT}", collected_text)
    logger.info(
        f"  extract_per_batch: 입력 {len(all_items)}건 (미뉴스 {len(batches.get('us_news',[]))} + 한뉴스 {len(batches.get('kr_news',[]))}), "
        f"prompt {len(prompt):,}자"
    )
    result = _parse_json_with_retry(client, prompt)
    pre_total = sum(len(result.get(b, {}).get(f, [])) for b in ("us_news","kr_news") for f in ("stocks","sectors"))
    result = _normalize_aliases_in_extraction(result)
    post_alias = sum(len(result.get(b, {}).get(f, [])) for b in ("us_news","kr_news") for f in ("stocks","sectors"))
    result = _filter_indices_from_extraction(result)
    post_filter = sum(len(result.get(b, {}).get(f, [])) for b in ("us_news","kr_news") for f in ("stocks","sectors"))
    logger.info(f"  extract_per_batch: LLM 출력 {pre_total} → 별칭 통합 {post_alias} → 인덱스 필터 {post_filter}")
    return result


def select_top3(extraction: Dict, client) -> Dict:
    """AI 콜 #2 — 영역별 TOP3 선정."""
    template = _load_prompt("trend_top3.txt")
    prompt = template.replace("{EXTRACTION_RESULT}", json.dumps(extraction, ensure_ascii=False, indent=2))
    logger.info(f"  select_top3: prompt {len(prompt):,}자, min(US)={MIN_STOCK_FREQ_US}/{MIN_SECTOR_FREQ_US}, min(KR)={MIN_STOCK_FREQ_KR}/{MIN_SECTOR_FREQ_KR}")
    result = _parse_json_with_retry(client, prompt)
    pre = {k: len(result.get(k, [])) for k in ("us_top3_sectors","us_top3_stocks","kr_top3_sectors","kr_top3_stocks")}
    result = _filter_indices_from_top3(result)
    result = _enforce_min_freq_top3(result)
    post = {k: len(result.get(k, [])) for k in ("us_top3_sectors","us_top3_stocks","kr_top3_sectors","kr_top3_stocks")}
    logger.info(f"  select_top3: LLM {pre} → 필터 후 {post}")
    return result


def _has_any_top3_entry(top3: Dict) -> bool:
    for key in ("us_top3_sectors", "us_top3_stocks", "kr_top3_sectors", "kr_top3_stocks"):
        if top3.get(key):
            return True
    return False


def _has_any_yt_top3_entry(yt_top3: Dict | None) -> bool:
    if not yt_top3:
        return False
    return bool(yt_top3.get("top3_sectors") or yt_top3.get("top3_stocks"))


def analyze_youtube(videos, client) -> Dict:
    """유튜브 영상 → TOP3 종목·섹터 추출."""
    if not videos:
        logger.info("  analyze_youtube: 입력 영상 0건 — 스킵")
        return {"top3_sectors": [], "top3_stocks": []}
    template = _load_prompt("youtube_trend.txt")
    parts = []
    for i, v in enumerate(videos, start=1):
        ts = v.published_at.strftime("%Y-%m-%d")
        body = v.transcript or v.description or "(자막·설명 없음)"
        parts.append(f"[영상#{i}] [{v.channel_name}] {ts} — {v.title}\n{body[:3000]}")
    videos_text = "\n\n".join(parts)
    prompt = template.replace("{VIDEOS_TEXT}", videos_text)
    transcript_count = sum(1 for v in videos if v.transcript)
    logger.info(
        f"  analyze_youtube: 입력 {len(videos)}개 영상 (자막 있음 {transcript_count}개), "
        f"prompt {len(prompt):,}자"
    )
    result = _parse_json_with_retry(client, prompt)
    # 자막 부실(YouTube 봇 차단) 환경 대응 — 임계값 완화
    min_yt_strong = 2   # 3 → 2 (10영상 중 20%)
    min_yt_visible = 1  # 1영상 언급도 약한 시그널로 노출 (자막 보강 전 임시)

    def _yt_freq(e):
        return max(e.get("freq", 0) or 0, len(e.get("refs", []) or []))

    for key in ("top3_sectors", "top3_stocks"):
        entries = result.get(key, [])
        kept, weak, dropped = [], 0, 0
        for e in entries:
            if _is_index_or_market(e.get("name", "")):
                dropped += 1
                continue
            f = _yt_freq(e)
            # prompt가 출력하는 summary 필드를 프론트 entry.reason 표기로 매핑
            if not e.get("reason") and e.get("summary"):
                e["reason"] = e["summary"]
            if f >= min_yt_strong:
                kept.append(e)
            elif f >= min_yt_visible:
                e["_weak_signal"] = True
                kept.append(e)
                weak += 1
            else:
                dropped += 1
        if dropped:
            logger.info(f"  필터: youtube.{key} 잡음 {dropped}건 제거 (인덱스/<{min_yt_visible}건)")
        if weak:
            logger.info(f"  약한 시그널: youtube.{key} {weak}건")
        result[key] = kept
    return result


def generate_outlook(top3: Dict, client, yt_top3: Dict | None = None) -> Dict:
    """AI 콜 #3 — us/kr TOP3 12개 + 유튜브 TOP3 최대 6개 항목 1주일 전망 (Google Search grounding).

    yt_top3는 None 또는 빈 dict일 수 있음 (유튜브 분석 실패 시).
    그 경우 prompt에 빈 구조를 전달하고 yt_*_outlook은 빈 배열로 응답되도록 지시.
    """
    if not _has_any_top3_entry(top3) and not _has_any_yt_top3_entry(yt_top3):
        logger.info("  generate_outlook: TOP3 결과 없음 — 스킵")
        return {}
    template = _load_prompt("trend_outlook.txt")
    yt_payload = yt_top3 or {"top3_sectors": [], "top3_stocks": []}
    prompt = template.replace("{TOP3_RESULT}", json.dumps(top3, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{YT_TOP3_RESULT}", json.dumps(yt_payload, ensure_ascii=False, indent=2))
    total_entries = (
        sum(len(top3.get(k, [])) for k in ("us_top3_sectors","us_top3_stocks","kr_top3_sectors","kr_top3_stocks"))
        + sum(len(yt_payload.get(k, [])) for k in ("top3_sectors","top3_stocks"))
    )
    logger.info(f"  generate_outlook: 입력 {total_entries}개 항목 (us/kr+yt), prompt {len(prompt):,}자, search grounding=ON")
    return _parse_json_with_retry(client, prompt, enable_search=True)


def merge_related_news_into_top3(top3: Dict, batches: Dict[str, List[CollectedItem]], max_per_entry: int = 5) -> Dict:
    """top3 entry의 *_news_refs 인덱스를 raw items와 매핑하여 related_news 필드로 추가.

    프론트가 entry.related_news를 그대로 표시하면 "근거 뉴스 보기" 펼치기로 노출.
    인덱스 번호(#1, #2)를 사용자에게 보이지 않게 하는 핵심 개선.
    """
    pairs = [
        ("us_top3_sectors", "us_news_refs", "us_news"),
        ("us_top3_stocks",  "us_news_refs", "us_news"),
        ("kr_top3_sectors", "kr_news_refs", "kr_news"),
        ("kr_top3_stocks",  "kr_news_refs", "kr_news"),
    ]
    enriched = 0
    for top3_key, refs_key, batch_key in pairs:
        idx_to_item = {it.idx: it for it in batches.get(batch_key, [])}
        for e in top3.get(top3_key, []):
            refs = e.get(refs_key, []) or []
            news = []
            for ref in refs[:max_per_entry]:
                it = idx_to_item.get(ref)
                if not it:
                    continue
                news.append({
                    "title": it.title,
                    "title_ko": getattr(it, "title_ko", "") or "",
                    "url": it.url,
                    "published_at": it.published_at.astimezone(
                        timezone(timedelta(hours=9))
                    ).strftime("%Y-%m-%d %H:%M:%S KST"),
                })
            if news:
                e["related_news"] = news
                enriched += 1
    logger.info(f"  merge_related_news: {enriched}개 entry에 근거 뉴스 머지 (최대 {max_per_entry}건/entry)")
    return top3


def merge_related_videos_into_youtube(yt_top3: Dict, videos, max_per_entry: int = 8) -> Dict:
    """yt_top3 entry의 refs(영상 인덱스 1-base)를 videos 리스트와 매핑해 related_videos 필드 추가.

    프론트는 entry.related_videos를 모달 리스트에 그대로 표시.
    """
    kst = timezone(timedelta(hours=9))
    enriched = 0
    for key in ("top3_sectors", "top3_stocks"):
        for e in yt_top3.get(key, []) or []:
            refs = e.get("refs", []) or []
            mapped = []
            for ref in refs[:max_per_entry]:
                try:
                    idx = int(ref) - 1  # prompt는 1-base
                except (TypeError, ValueError):
                    continue
                if idx < 0 or idx >= len(videos):
                    continue
                v = videos[idx]
                mapped.append({
                    "title": getattr(v, "title", ""),
                    "url": getattr(v, "url", ""),
                    "channel_name": getattr(v, "channel_name", ""),
                    "published_at": getattr(v, "published_at", None).astimezone(kst).strftime("%Y-%m-%d %H:%M:%S KST")
                        if getattr(v, "published_at", None) else "",
                })
            if mapped:
                e["related_videos"] = mapped
                enriched += 1
    logger.info(f"  merge_related_videos: {enriched}개 entry에 영상 URL 머지 (최대 {max_per_entry}건/entry)")
    return yt_top3


def merge_outlook_into_top3(top3: Dict, outlook: Dict, yt_top3: Dict | None = None) -> Dict:
    """outlook 응답의 *_outlook 배열을 top3 / yt_top3 entry의 outlook 필드로 머지.

    LLM 응답 형식:
      {"us_sector_outlook": [{"name":"AI","outlook":"..."},...], "us_stock_outlook": [...], ...,
       "yt_sector_outlook": [...], "yt_stock_outlook": [...]}
    us/kr는 top3, youtube는 yt_top3 entry에 각각 outlook 필드로 추가 (name 매칭).
    """
    pairs_main = [
        ("us_sector_outlook", "us_top3_sectors"),
        ("us_stock_outlook",  "us_top3_stocks"),
        ("kr_sector_outlook", "kr_top3_sectors"),
        ("kr_stock_outlook",  "kr_top3_stocks"),
    ]
    merged = 0
    for ok, tk in pairs_main:
        outlook_map = {(e.get("name") or "").strip(): (e.get("outlook") or "").strip()
                       for e in outlook.get(ok, []) if e.get("name")}
        for e in top3.get(tk, []):
            text = outlook_map.get((e.get("name") or "").strip())
            if text:
                e["outlook"] = text
                merged += 1
    if yt_top3 is not None:
        for ok, tk in (("yt_sector_outlook", "top3_sectors"), ("yt_stock_outlook", "top3_stocks")):
            outlook_map = {(e.get("name") or "").strip(): (e.get("outlook") or "").strip()
                           for e in outlook.get(ok, []) if e.get("name")}
            for e in yt_top3.get(tk, []):
                text = outlook_map.get((e.get("name") or "").strip())
                if text:
                    e["outlook"] = text
                    merged += 1
    logger.info(f"  merge_outlook: {merged}개 entry에 outlook 머지")
    return top3
