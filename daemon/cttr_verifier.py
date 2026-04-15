"""호가잔량 OFI 필터 실효성 자동 검증 — 10거래일 데이터 누적 시 분석 + 리포트 + 텔레그램.

실행 조건:
- results/cttr_log/*.json 파일 수 ≥ 10 (10거래일)
- results/cttr_log/_verified 마커 파일 없음 (1회만 실행)

분석 내용:
- 시점별(0905/0910/0915) ofi_ratio와 final_pnl 상관관계
- ofi_ratio > 1.0 vs < 1.0 그룹 비교
- 임계값별(1.0/1.5/2.0) 필터 효과 시뮬
- 결론: 필터 도입 권고 여부 + 최적 임계값
"""
import json
import logging
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))
LOG_DIR = Path(__file__).parent.parent / "results" / "cttr_log"
REPORT_DIR = Path(__file__).parent.parent / "docs" / "research"
MARKER = LOG_DIR / "_verified"
MIN_DAYS = 10  # 최소 분석 거래일


def _load_logs() -> list[dict]:
    """모든 cttr_log 파일을 로드 → 단일 candidate 리스트로 평탄화."""
    rows = []
    if not LOG_DIR.exists():
        return rows
    for p in sorted(LOG_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            date = data.get("date", p.stem)
            for code, info in data.get("candidates", {}).items():
                final_pnl = info.get("final_pnl_pct")
                if final_pnl is None:
                    continue
                snaps = info.get("snapshots", {})
                rows.append({
                    "date": date,
                    "code": code,
                    "name": info.get("name", ""),
                    "selected": info.get("selected", False),
                    "final_pnl": final_pnl,
                    "snap_0905": snaps.get("0905", {}),
                    "snap_0910": snaps.get("0910", {}),
                    "snap_0915": snaps.get("0915", {}),
                })
        except Exception as e:
            logger.warning(f"cttr_log 로드 오류 ({p.name}): {e}")
    return rows


def _analyze_snapshot(rows: list[dict], snap_key: str) -> dict:
    """특정 시점의 ofi_ratio가 final_pnl을 예측하는지 분석."""
    pairs = []
    for r in rows:
        snap = r.get(snap_key, {})
        ofi = snap.get("ofi_ratio")
        if ofi is None or ofi <= 0:
            continue
        pairs.append((ofi, r["final_pnl"]))

    if len(pairs) < 5:
        return {"n": len(pairs), "valid": False}

    # 임계값별 그룹 비교
    threshold_results = []
    for thr in [0.7, 1.0, 1.3, 1.5, 2.0]:
        above = [p for o, p in pairs if o >= thr]
        below = [p for o, p in pairs if o < thr]
        if not above or not below:
            continue
        threshold_results.append({
            "threshold": thr,
            "above_n": len(above),
            "above_avg": round(statistics.mean(above), 2),
            "above_win_rate": round(sum(1 for x in above if x > 0) / len(above) * 100, 1),
            "below_n": len(below),
            "below_avg": round(statistics.mean(below), 2),
            "below_win_rate": round(sum(1 for x in below if x > 0) / len(below) * 100, 1),
            "diff": round(statistics.mean(above) - statistics.mean(below), 2),
        })

    # Pearson 상관계수
    try:
        ofis = [o for o, _ in pairs]
        pnls = [p for _, p in pairs]
        n = len(pairs)
        mean_o = sum(ofis) / n
        mean_p = sum(pnls) / n
        cov = sum((o - mean_o) * (p - mean_p) for o, p in pairs) / n
        std_o = (sum((o - mean_o) ** 2 for o in ofis) / n) ** 0.5
        std_p = (sum((p - mean_p) ** 2 for p in pnls) / n) ** 0.5
        corr = round(cov / (std_o * std_p), 3) if (std_o > 0 and std_p > 0) else 0
    except Exception:
        corr = 0

    return {
        "n": len(pairs),
        "valid": True,
        "correlation": corr,
        "thresholds": threshold_results,
        "all_avg": round(statistics.mean([p for _, p in pairs]), 2),
        "all_win_rate": round(sum(1 for _, p in pairs if p > 0) / len(pairs) * 100, 1),
    }


def _generate_report(rows: list[dict], analyses: dict) -> tuple[str, str]:
    """MD 리포트 + 텔레그램 요약 생성."""
    today = datetime.now(_KST).strftime("%Y-%m-%d")
    days = sorted(set(r["date"] for r in rows))
    n_days = len(days)
    n_total = len(rows)
    n_selected = sum(1 for r in rows if r["selected"])

    md_lines = [
        f"# 호가잔량 OFI 필터 실효성 검증 결과",
        f"",
        f"> 분석일: {today} | 누적 데이터: {n_days}거래일 ({days[0]}~{days[-1]}) | 총 {n_total}건",
        f"> 선정된 매수 종목: {n_selected}건 | 후보 (미선정): {n_total - n_selected}건",
        f"",
        f"## 시점별 OFI 예측력",
        f"",
    ]

    tg_lines = [
        f"<b>📊 OFI 필터 검증 ({n_days}거래일)</b>",
        f"",
    ]

    best_snap = None
    best_diff = -999

    for snap_key, snap_label in [("snap_0905", "09:05"), ("snap_0910", "09:10"), ("snap_0915", "09:15")]:
        a = analyses[snap_key]
        md_lines.append(f"### {snap_label} 시점")
        md_lines.append("")
        if not a.get("valid"):
            md_lines.append(f"⚠️ 데이터 부족 (n={a['n']})")
            md_lines.append("")
            continue

        md_lines.append(f"- 분석 표본: {a['n']}건")
        md_lines.append(f"- Pearson 상관계수 (OFI vs final_pnl): **{a['correlation']:+.3f}**")
        md_lines.append(f"- 전체 평균 수익률: {a['all_avg']:+.2f}% (승률 {a['all_win_rate']:.1f}%)")
        md_lines.append("")
        md_lines.append("| 임계값 | OFI≥thr (n, 평균, 승률) | OFI<thr (n, 평균, 승률) | 차이 |")
        md_lines.append("|--------|------------------------|------------------------|------|")
        for tr in a["thresholds"]:
            md_lines.append(
                f"| {tr['threshold']:.1f} | {tr['above_n']}, {tr['above_avg']:+.2f}%, {tr['above_win_rate']:.0f}% | "
                f"{tr['below_n']}, {tr['below_avg']:+.2f}%, {tr['below_win_rate']:.0f}% | "
                f"**{tr['diff']:+.2f}%p** |"
            )
            if tr["diff"] > best_diff:
                best_diff = tr["diff"]
                best_snap = (snap_label, tr)
        md_lines.append("")

    # 결론
    md_lines.append("## 결론")
    md_lines.append("")
    if best_snap and best_diff > 1.0:
        snap_label, tr = best_snap
        md_lines.append(f"✅ **OFI 필터 도입 권고**")
        md_lines.append(f"- 최적: {snap_label} 시점, OFI ≥ {tr['threshold']:.1f}")
        md_lines.append(f"- 효과: 평균 수익률 {tr['above_avg']:+.2f}% (필터 제외 종목 평균 {tr['below_avg']:+.2f}%)")
        md_lines.append(f"- 차이: **{best_diff:+.2f}%p**")
        tg_lines.append(f"✅ <b>필터 도입 권고</b>")
        tg_lines.append(f"최적: {snap_label} OFI≥{tr['threshold']:.1f}")
        tg_lines.append(f"효과: {tr['above_avg']:+.2f}% vs {tr['below_avg']:+.2f}% (차이 {best_diff:+.2f}%p)")
    elif best_snap and best_diff > 0:
        snap_label, tr = best_snap
        md_lines.append(f"⚠️ **OFI 효과 미미 (도입 보류)**")
        md_lines.append(f"- 최선: {snap_label} OFI ≥ {tr['threshold']:.1f}, 차이 {best_diff:+.2f}%p")
        md_lines.append(f"- 통계적 유의성 부족, 추가 데이터 누적 후 재검증 권장")
        tg_lines.append(f"⚠️ <b>효과 미미</b>")
        tg_lines.append(f"최선: {snap_label} OFI≥{tr['threshold']:.1f}, 차이 {best_diff:+.2f}%p")
    else:
        md_lines.append(f"❌ **OFI 필터 무효**")
        md_lines.append(f"- 모든 임계값에서 OFI 필터의 예측력 없음")
        md_lines.append(f"- 09:05 호가잔량은 노이즈가 큼 (학술 가설 부합)")
        tg_lines.append(f"❌ <b>OFI 필터 무효</b>")

    md = "\n".join(md_lines)
    tg = "\n".join(tg_lines)
    return md, tg


async def verify_and_report():
    """검증 + MD 저장 + 텔레그램 전송 (3일 연속, 같은 시각)."""
    # 발송 횟수 확인 (마커에 "N" 저장, N=1,2,3)
    send_count = 0
    if MARKER.exists():
        try:
            content = MARKER.read_text(encoding="utf-8").strip()
            # 기존 포맷 호환: "YYYY-MM-DD" → 1회 완료로 간주
            if content.isdigit():
                send_count = int(content)
            elif content:
                send_count = 1
        except Exception:
            pass
    if send_count >= 3:
        return False  # 3회 완료

    if not LOG_DIR.exists():
        return False
    log_files = [p for p in LOG_DIR.glob("*.json") if not p.name.startswith("_")]
    if len(log_files) < MIN_DAYS:
        logger.info(f"cttr_log 데이터 부족 ({len(log_files)}/{MIN_DAYS}거래일) — 검증 보류")
        return False

    logger.info(f"OFI 필터 검증 ({send_count+1}/3회차) — {len(log_files)}거래일 데이터")
    rows = _load_logs()
    if not rows:
        logger.warning("OFI 검증: 유효 데이터 없음")
        return False

    analyses = {
        "snap_0905": _analyze_snapshot(rows, "snap_0905"),
        "snap_0910": _analyze_snapshot(rows, "snap_0910"),
        "snap_0915": _analyze_snapshot(rows, "snap_0915"),
    }
    md, tg = _generate_report(rows, analyses)

    # MD 저장 (1회차만)
    today = datetime.now(_KST).strftime("%Y-%m-%d")
    if send_count == 0:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIR / f"{today}-ofi-verification.md"
        report_path.write_text(md, encoding="utf-8")
        logger.info(f"OFI 검증 리포트 저장: {report_path}")

    # 텔레그램 전송 (회차 표시 추가)
    tg_with_count = f"<b>[OFI 검증 {send_count+1}/3]</b>\n" + tg
    try:
        from daemon.trader import send_telegram
        await send_telegram(tg_with_count)
    except Exception as e:
        logger.warning(f"OFI 검증 텔레그램 전송 실패: {e}")

    # 발송 횟수 업데이트
    MARKER.write_text(str(send_count + 1), encoding="utf-8")
    return True
