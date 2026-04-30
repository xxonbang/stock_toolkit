"""Gemini AI 클라이언트 — 다중 키 폴백 + 재시도 (Stock Insight 전용).

trade_info_sender의 ai_researcher.py를 단순화하여 이식.
- GOOGLE_API_KEY_01 ~ GOOGLE_API_KEY_05 환경변수에서 자동 로드 (있는 만큼)
- 첫 키 quota 소진 시 다음 키로 자동 폴백
- DNS/timeout/503/Rate Limit/Quota 분기 처리
- enable_search=True 시 Google Search grounding 활성화
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Dict, Tuple

# gRPC DNS 리졸버 (DNS 실패 회피)
os.environ.setdefault("GRPC_DNS_RESOLVER", "native")
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash-lite"  # free tier RPD 1000+, search grounding 지원


class GeminiClient:
    """다중 키 폴백 Gemini 클라이언트."""

    def __init__(self) -> None:
        self.keys = [os.getenv(f"GOOGLE_API_KEY_{i:02d}") for i in range(1, 6)]
        self.keys = [k for k in self.keys if k]
        if not self.keys:
            raise RuntimeError("GOOGLE_API_KEY_01~05 중 최소 1개 환경변수 필요")
        self._idx = 0
        self._exhausted: set[int] = set()
        self.model_name = MODEL_NAME
        # 호출 통계
        self._call_count = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_retries = 0
        self._total_fallbacks = 0
        self._init_client()

    def _init_client(self) -> None:
        from google import genai
        self.client = genai.Client(api_key=self.keys[self._idx])
        logger.info(f"Gemini 클라이언트 초기화 (키 #{self._idx + 1:02d}/{len(self.keys)}): {self.model_name}")

    def _switch_to_next(self) -> bool:
        """현재 키를 소진 마킹 + 다음 가용 키로 전환. 모두 소진이면 False."""
        self._exhausted.add(self._idx)
        for i in range(len(self.keys)):
            if i not in self._exhausted:
                self._idx = i
                self._init_client()
                self._total_fallbacks += 1
                logger.info(f"키 폴백 → #{self._idx + 1:02d} (누적 폴백 {self._total_fallbacks}회)")
                return True
        return False

    def summary(self) -> None:
        """LLM 호출 통계 요약 (파이프라인 종료 시 호출)."""
        logger.info("📈 Gemini 호출 통계:")
        logger.info(f"  총 호출: {self._call_count}회")
        logger.info(f"  prompt tokens: {self._total_prompt_tokens:,}, completion tokens: {self._total_completion_tokens:,}")
        logger.info(f"  재시도 발생: {self._total_retries}회, 키 폴백: {self._total_fallbacks}회")
        logger.info(f"  사용한 키 인덱스: #{self._idx + 1:02d}/{len(self.keys)} (소진된 키: {sorted(self._exhausted)})")

    def call(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_output_tokens: int = 6000,
        system_instruction: str | None = None,
        enable_search: bool = False,
        max_retries: int = 3,
    ) -> Tuple[str, Dict]:
        """LLM 호출. (응답 텍스트, 토큰 사용량) 반환. 실패 시 sentinel 문자열 반환."""
        from google.genai import types

        config_params: Dict = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "topP": 0.9,
        }
        if system_instruction:
            config_params["systemInstruction"] = system_instruction
        if enable_search:
            config_params["tools"] = [types.Tool(google_search=types.GoogleSearch())]
            logger.info("🔎 Google Search grounding 활성화")
        gen_config = types.GenerateContentConfig(**config_params)

        # 호출 진단 로그 (DEBUG가 prompt 일부 일부 표시)
        self._call_count += 1
        prompt_len = len(prompt)
        logger.info(
            f"💬 LLM call #{self._call_count}: prompt {prompt_len:,}자, "
            f"temp={temperature}, max_tokens={max_output_tokens}, search={enable_search}, key=#{self._idx + 1:02d}"
        )
        logger.debug(f"   prompt 앞 200자: {prompt[:200]!r}")

        t_start = time.time()
        attempt = 0
        while attempt < max_retries:
            try:
                if attempt > 0:
                    time.sleep(2)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=gen_config,
                )
                text = getattr(response, "text", "") or ""
                usage_meta = getattr(response, "usage_metadata", None)
                usage = {}
                if usage_meta is not None:
                    usage = {
                        "prompt_tokens": getattr(usage_meta, "prompt_token_count", 0),
                        "completion_tokens": getattr(usage_meta, "candidates_token_count", 0),
                        "total_tokens": getattr(usage_meta, "total_token_count", 0),
                    }
                    self._total_prompt_tokens += usage["prompt_tokens"]
                    self._total_completion_tokens += usage["completion_tokens"]
                # finish_reason 확인 (비정상 종료 추적)
                fin = "?"
                if hasattr(response, "candidates") and response.candidates:
                    fin = str(getattr(response.candidates[0], "finish_reason", "?"))
                logger.info(
                    f"✓ LLM call #{self._call_count} 완료 ({time.time()-t_start:.2f}s): "
                    f"응답 {len(text):,}자, tokens(in/out)={usage.get('prompt_tokens',0)}/{usage.get('completion_tokens',0)}, "
                    f"finish={fin}"
                )
                logger.debug(f"   응답 앞 200자: {text[:200]!r}")
                return text, usage
            except Exception as e:
                err = str(e)
                is_dns = "DNS" in err or "C-ares" in err
                is_timeout = "timeout" in err.lower() or "Timeout" in err
                is_503 = "503" in err or "overloaded" in err.lower() or "UNAVAILABLE" in err
                is_quota = (
                    "quota" in err.lower()
                    or "429" in err
                    or "exceeded your current quota" in err.lower()
                )
                is_rate_limit = "429" in err and "rate limit" in err.lower() and not is_quota

                if is_quota:
                    # retryDelay 짧으면 RPM 한도 → wait + retry 같은 키
                    m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)\s*s", err)
                    delay_s = int(m.group(1)) if m else None
                    if delay_s is not None and delay_s < 60 and attempt < max_retries - 1:
                        wait = delay_s + 5
                        logger.warning(f"⚠️ RPM 한도, {wait}s wait + same-key retry")
                        time.sleep(wait)
                        attempt += 1
                        self._total_retries += 1
                        continue
                    # daily quota 추정 → 다음 키
                    if self._switch_to_next():
                        attempt = 0
                        continue
                    logger.error("❌ 모든 Gemini 키 quota 소진")
                    return "API 할당량 초과(429 Error)", {}
                if (is_dns or is_timeout or is_503) and attempt < max_retries - 1:
                    waits = [5, 10, 20, 30, 60]
                    w = waits[min(attempt, len(waits) - 1)]
                    label = "DNS" if is_dns else ("timeout" if is_timeout else "503")
                    logger.warning(f"⚠️ {label} 에러 — {w}s 대기 후 재시도 ({attempt + 1}/{max_retries})")
                    time.sleep(w)
                    attempt += 1
                    self._total_retries += 1
                    continue
                if is_rate_limit and attempt < max_retries - 1:
                    waits = [10, 30, 60, 120, 180]
                    w = waits[min(attempt, len(waits) - 1)]
                    logger.warning(f"⚠️ Rate limit — {w}s 대기 ({attempt + 1}/{max_retries})")
                    time.sleep(w)
                    attempt += 1
                    self._total_retries += 1
                    continue
                if attempt < max_retries - 1:
                    logger.warning(f"기타 에러 (재시도 {attempt + 1}/{max_retries}): {err[:200]}")
                    time.sleep(5)
                    attempt += 1
                    self._total_retries += 1
                    continue
                logger.error(f"AI 호출 최종 실패: {err[:300]}")
                return f"오류: {err[:500]}", {}
        return "오류: 최대 재시도 초과", {}


def create_client() -> GeminiClient:
    return GeminiClient()
