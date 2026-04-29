"""뉴스 제목 번역 — Gemini 배치 호출 (영→한).

us_news 50건의 영어 제목을 한 번의 LLM 콜로 일괄 번역.
실패 시 title_ko는 빈 문자열로 유지(프론트엔드는 영어만 표시).
"""
from __future__ import annotations

import json
import logging
import re
from typing import List

from modules.news.collectors.base import CollectedItem

logger = logging.getLogger(__name__)


_PROMPT = """다음 영어 뉴스 제목 {N}개를 자연스러운 한국어로 번역하라.

규칙:
- 입력 순서를 유지한 JSON 배열로만 출력 (다른 텍스트 금지).
- 회사명·티커·고유명사는 영어 그대로 보존 (예: Nvidia, Tesla, S&P 500).
- 의역보다 직역에 가깝게, 30자 이내 간결하게.
- 빈 항목 또는 번역 불가능한 항목은 "" (빈 문자열).

[입력 제목 배열]
{TITLES_JSON}

[출력 — JSON 배열만]
"""


def _strip_codeblock(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def translate_us_titles(items: List[CollectedItem], client) -> int:
    """영어 제목을 한국어로 일괄 번역하여 item.title_ko에 저장. 성공 개수 반환.

    실패 시 빈 문자열 유지(프론트엔드는 영어만 표시).
    """
    if not items:
        return 0
    titles = [it.title for it in items]
    prompt = _PROMPT.replace("{N}", str(len(titles))).replace(
        "{TITLES_JSON}", json.dumps(titles, ensure_ascii=False)
    )
    try:
        text, _ = client.call(
            prompt=prompt,
            temperature=0.0,
            max_output_tokens=8000,
        )
    except Exception as e:
        logger.warning(f"제목 번역 호출 실패: {e}")
        return 0

    if not text or text.startswith("오류:") or text.startswith("API 할당량 초과"):
        logger.warning(f"번역 응답 비정상: {text[:120]}")
        return 0

    cleaned = _strip_codeblock(text)
    # 응답이 JSON 배열로 시작하지 않으면 추출 시도
    m = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if m:
        cleaned = m.group(0)
    try:
        translations = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"번역 JSON 파싱 실패: {e}")
        return 0

    if not isinstance(translations, list):
        logger.warning("번역 결과가 배열이 아님")
        return 0

    success = 0
    for it, tr in zip(items, translations):
        if isinstance(tr, str) and tr.strip():
            it.title_ko = tr.strip()
            success += 1
    logger.info(f"제목 번역 성공: {success}/{len(items)}건")
    return success
