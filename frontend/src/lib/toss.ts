/** 토스증권 종목 deep link — AppsFlyer OneLink 통한 토스 앱 자동 분기.
 *  contents.tossinvest.com JS chunk(41105)의 deep link 로직을 그대로 재현. theme_lab StockDetailModal과 동일.
 *  - 모바일: supertoss:// 스킴으로 토스 앱 종목 화면 진입
 *  - 데스크탑: 기본 동작 유지 (웹 URL 새 탭) */

const ONELINK_BASE = "https://toss.onelink.me/3563614660";

/** 토스 웹 주문 화면 URL (데스크탑/폴백). */
export function tossWebUrl(code: string): string {
  return `https://www.tossinvest.com/stocks/A${code}/order`;
}

/** 토스 OneLink deep link URL — 모바일 클릭 시 토스 앱으로 자동 분기. */
export function buildTossDeepUrl(code: string): string {
  const nextLandingUrl = `/stocks/A${code}?utm_source=tosssec&utm_medium=wts_mobile&utm_campaign=stock_detail`;
  const service = `https://service.tossinvest.com?nextLandingUrl=${encodeURIComponent(nextLandingUrl)}`;
  const supertoss = `supertoss://securities?url=${encodeURIComponent(service)}&clearHistory=true&swipeRefresh=true`;
  const webFallback = `https://contents.tossinvest.com/stocks/A${code}`;
  const params = new URLSearchParams({
    pid: "referral",
    c: "conversion_securities_performance",
    af_param_forwarding: "false",
    af_dp: supertoss,
    af_force_deeplink: "true",
    af_web_dp: webFallback,
    af_r: webFallback,
  });
  return `${ONELINK_BASE}?${params.toString()}`;
}

/** <a href={tossWebUrl(code)} onClick={(e) => handleTossClick(code, e)}> 패턴용 클릭 핸들러.
 *  모바일에서만 deep link로 분기, 데스크탑은 기본 새 탭 동작 유지. */
export function handleTossClick(code: string, e: React.MouseEvent<HTMLAnchorElement>): void {
  const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  if (!isMobile) return;
  e.preventDefault();
  window.location.href = buildTossDeepUrl(code);
}
