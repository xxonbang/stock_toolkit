/**
 * 네이버 시간외 단일가 API
 * CORS 차단 시 console.error 후 null/빈 객체 반환 (KIS fallback 유지)
 */

export interface NaverQuote {
  code: string;
  closePrice: number;          // 정규장 종가
  changeAmount: number;        // 전일대비
  changeRate: number;          // 등락률 %
  overtimePrice?: number;      // 시간외 단일가 (있을 때만)
  overtimeStatus?: "OPEN" | "CLOSE";
  overtimeTradedAt?: string;
  highPrice?: number;
  lowPrice?: number;
}

/** 평일 15:30~18:00 KST 여부 */
export function isAfterhoursKR(): boolean {
  const now = new Date();
  // UTC+9 변환
  const kst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  const day = kst.getUTCDay(); // 0=Sun, 6=Sat
  if (day === 0 || day === 6) return false;
  const hh = kst.getUTCHours();
  const mm = kst.getUTCMinutes();
  const totalMin = hh * 60 + mm;
  return totalMin >= 15 * 60 + 30 && totalMin < 18 * 60;
}

export async function fetchNaverQuote(code: string): Promise<NaverQuote | null> {
  try {
    const res = await fetch(
      `https://polling.finance.naver.com/api/realtime/domestic/stock/${code}`,
      { headers: { "Accept": "application/json" } }
    );
    if (!res.ok) return null;
    const json = await res.json();
    const d = json?.datas?.[0];
    if (!d) return null;

    const closePrice = Number(d.closePriceRaw ?? 0);
    const changeAmount = Number(d.compareToPreviousClosePriceRaw ?? 0);
    const changeRate = Number(d.fluctuationsRatioRaw ?? d.fluctuationsRatio ?? 0);
    const omi = d.overMarketPriceInfo;
    const overtimeStatus = omi?.overMarketStatus as "OPEN" | "CLOSE" | undefined;
    const overtimePrice = omi?.overPrice ? Number(omi.overPrice) : undefined;

    return {
      code,
      closePrice,
      changeAmount,
      changeRate,
      overtimePrice: overtimeStatus === "OPEN" && overtimePrice ? overtimePrice : undefined,
      overtimeStatus,
      overtimeTradedAt: omi?.overTradedAt,
      highPrice: d.highPriceRaw ? Number(d.highPriceRaw) : undefined,
      lowPrice: d.lowPriceRaw ? Number(d.lowPriceRaw) : undefined,
    };
  } catch (e) {
    console.error(`[naver] fetchNaverQuote(${code}) 실패:`, e);
    return null;
  }
}

/** 복수 종목 병렬 조회. CORS 실패 시 빈 객체 반환 */
export async function fetchNaverQuotes(codes: string[]): Promise<Record<string, NaverQuote>> {
  const results = await Promise.allSettled(codes.map((c) => fetchNaverQuote(c)));
  const map: Record<string, NaverQuote> = {};
  results.forEach((r, i) => {
    if (r.status === "fulfilled" && r.value) map[codes[i]] = r.value;
  });
  return map;
}
