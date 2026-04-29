"""공통 타입 + 인덱스 라벨 유틸"""
from dataclasses import dataclass
from datetime import datetime
from typing import List


BATCH_LABELS = {
    "us_news": "미뉴스",
    "kr_news": "한뉴스",
    # 커뮤니티 배치(us_community/kr_community)는 잡담·작전성 비율로 비활성화 (2026-04-29)
}


@dataclass
class CollectedItem:
    """수집된 글 1건"""
    batch: str            # "us_news" | "kr_news"
    idx: int              # 1..50 (배치 내 일련번호)
    title: str
    body: str             # 요약 또는 본문 일부 (1000자 이내 권장, HTML 태그 제거됨)
    url: str
    published_at: datetime  # tz-aware
    title_ko: str = ""    # 한국어 번역 (us_news만 채워짐, 번역 실패 시 빈 문자열)


def label_for_batch(batch: str) -> str:
    """배치 키 → 한글 라벨"""
    return BATCH_LABELS[batch]


def format_indexed_text(items: List[CollectedItem]) -> str:
    """LLM 입력용 텍스트로 직렬화. [라벨#N] 제목\\n본문 형태."""
    lines = []
    for it in items:
        lbl = label_for_batch(it.batch)
        lines.append(f"[{lbl}#{it.idx}] {it.title}\n{it.body}")
    return "\n\n".join(lines)
