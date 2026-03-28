# 구현 계획 — 확정 사실 기반

> 작성일: 2026-03-28 KST
> 근거: `2026-03-28-dashboard-evaluation.md` 확정 사실 6건
> 범위: 모의투자 기능 제외

---

## 작업 목록

### 1. D등급 7개 섹션 제거

**근거**: 하드코딩/플레이스홀더, daemon 의존성 0건 확인 (1차, 12차 6)

**변경 파일:**
- `frontend/src/pages/Dashboard.tsx` — state 6개 + fetch 6개 + JSX 6개 섹션 제거 (~152줄)
- `frontend/src/services/dataService.ts` — fetch 함수 6개 제거
- `frontend/src/components/HelpDialog.tsx` — 해당 섹션 도움말 텍스트 제거

**제거 대상:**
1. 컨센서스 괴리 (consensus)
2. 동시호가 분석 (auction)
3. 이벤트 캘린더 (eventCalendar)
4. 테마 전이 예측 (propagation)
5. 손절/익절 최적화 (exitOptimizer)
6. 내부자 거래 (insiderTrades)

**검증**: TypeScript 빌드 에러 0건 + 전체 테스트 통과 확인

---

### 2. test_cross_signal.py 2건 실패 수정

**근거**: dual_signal 명칭 변경 후 테스트 미동기화 (4차 9, 12차 5)

**변경 파일**: `tests/test_cross_signal.py`

**수정 내용:**
- `test_find_cross_signals`: `len(result) == 1` → `len(result) == 2` (UNION 로직), `dual_signal` 기대값을 "쌍방매수"/"Vision매수" 등으로 변경
- `test_find_cross_signals_no_match`: `len(result) == 0` → `len(result) == 2`, "Vision매수"/"대장주" 기대값 추가

**검증**: `python -m pytest tests/test_cross_signal.py -v` 3건 통과

---

### 3. 시그널 데이터 공개 접근 검토

**근거**: 53개 JSON 무인증 공개, HTTP 200 실증 (4차 1, 12차 7)

**선택지:**
- A) 레포를 private으로 전환 (GitHub Pages는 Pro 필요)
- B) 데이터를 Supabase로 이동, 인증 후 접근
- C) 현행 유지 + 면책 문구 추가 (모의투자/연구 목적)

**판단 필요**: 사용자가 선택

---

## 구현하지 않는 것 (근거 부족)

| 항목 | 이유 |
|------|------|
| 5팩터 배점 재조정 | 42일 데이터로 판단 불가, T+N 인프라 선행 필요 |
| Confidence 역방향 적용 | 통계적으로 유의하나 2개월 데이터, 범용성 미확인 |
| API-only 우선 전략 | p=0.069 경계선, 5% 미달 |
| 저가주 필터 강화 | 기간 의존적 (2월↔3월 방향 반대) |
| 매도 시그널 활용 | 아웃라이어 제거 시 효과 소멸 |
| Exit 전략 변경 (SL/TP) | 모의투자 카테고리 제외 |

---

## 실행 순서

```
1. test_cross_signal.py 수정 (10분)
   → pytest 통과 확인

2. D등급 7개 섹션 제거 (30분)
   → TypeScript 빌드 확인
   → 전체 테스트 확인

3. 커밋 + 푸시

4. 시그널 공개 접근 → 사용자 판단 대기
```
