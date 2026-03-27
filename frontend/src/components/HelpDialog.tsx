import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { HelpCircle, X } from "lucide-react";

export const SECTION_HELP: Record<string, { title: string; desc: string }> = {
  briefing: {
    title: "AI 모닝 브리핑",
    desc: "Gemini AI가 시장 데이터를 종합 분석하여 매일 아침 작성하는 투자 브리핑입니다. 글로벌 환경, 주목 테마, 고확신 종목, 전략 제안을 포함합니다.",
  },
  market: {
    title: "시장 현황",
    desc: "공포·탐욕 지수(Fear & Greed)는 시장 심리를 0~100으로 측정합니다. 25 미만은 극단적 공포(매수 기회), 75 이상은 극단적 탐욕(과열 주의)입니다. VIX는 S&P 500 옵션 기반 변동성 지수로, 12 미만은 극저변동(안정), 12~20은 정상, 20~30은 불안(경계), 30 이상은 공포(급변동)입니다. 환율, F&G 추세, 글로벌 매크로 8개 지표, AI 테마 예측, 매크로 추세 히스토리를 종합 표시합니다.",
  },
  signals: {
    title: "AI 주목 종목",
    desc: "AI 분석 결과 매수 신호가 있는 종목을 신뢰도 순으로 분류합니다.\n\n■ 카테고리 분류 기준\n· 고확신: 테마 대장주 + Vision AI 매수 + KIS API 매수 (두 독립 분석 일치)\n· 대장주: 테마 대장주(교차 신호)이지만 한쪽만 매수 또는 한쪽이 중립\n· 매수 일치: 대장주는 아니지만 Vision AI와 KIS API 양쪽 모두 매수\n· 매수: 한쪽(Vision 또는 KIS)만 매수 신호\n\n■ 대장주란?\n테마 분석에서 해당 테마를 대표하는 종목으로 선정된 주식입니다. 교차 신호(cross_signal) 데이터에 포함된 종목이 대장주입니다.\n\n■ 뱃지\n· N일 연속: 연속으로 매수 신호가 발생한 일수\n· 외인↑/↓: 외국인 순매수/순매도 방향",
  },
  cross: {
    title: "교차 신호",
    desc: "테마 분석(대장주)과 기술적 분석(매수 신호)이 동시에 일치하는 종목입니다.\n\n■ 신호 검증 상태\n· 신호 유효: AI 분석 방향대로 가격이 움직이는 중 (매수→상승, 매도→하락)\n· 중립: 소폭 변동(-2%~0%), 아직 판단 보류\n· 신호 약화: 분석 반대 방향으로 -2%~-5% 이동 중 → 주의\n· 신호 무효화: 분석 반대 방향으로 -5% 이상 이동 → 신호 틀림, 재검토 필요\n\n■ 신호 나이: 신호 생성 후 경과 시간. 오래될수록 신뢰도 감소.\n■ 장중 변화율: 오늘 시가 대비 현재 등락률.",
  },
  lifecycle: {
    title: "테마 라이프사이클",
    desc: "각 테마의 생명주기 단계를 분류합니다. 탄생(초기 진입 기회) → 성장(추세 추종) → 과열(신규 진입 자제) → 쇠퇴(정리). 평균 등락률은 테마 내 대장주들의 당일 평균 수익률입니다.",
  },
  anomaly: {
    title: "이상 거래 감지",
    desc: "거래량 폭발(평소 대비 N배 이상)이나 가격 급변(당일 등락률 10% 이상) 등 비정상적 거래 패턴을 탐지합니다. 뉴스나 재료가 반영되기 전에 수급 변화를 포착할 수 있습니다.",
  },
  risk: {
    title: "위험 종목 모니터",
    desc: "AI 분석 결과 위험 요인이 감지된 종목입니다.\n\n■ 위험 요인\n· 매도 신호: AI 차트 분석(vision)이 '매도' 또는 '적극매도'로 판단한 종목\n· 외국인 대량 매도: 외국인 순매도 10만주 이상\n· RSI 과매수: RSI 70 이상 → 단기 과열 구간\n\n■ 위험 등급\n· 위험: level 높음 + 경고 2개 이상\n· 경고: level 높음 또는 경고 2개\n· 주의: 경고 1개\n\n보유 종목이 포함되면 최상단에 강조 표시됩니다.",
  },
  smartmoney: {
    title: "스마트 머니 TOP",
    desc: "외국인·기관 투자자의 매수 패턴을 종합 평가한 스코어(0~99)입니다. 70점 이상만 표시됩니다.\n\n■ 점수 구성 (기본 50점 + 가산)\n· Vision AI 신호: 적극매수 +30, 매수 +15\n· KIS API 신호: 적극매수 +20, 매수 +10\n· AI 신뢰도: confidence(0~1) × 20 = 최대 +20\n· 외국인 순매수: 순매수 > 0이면 +10\n· 이중 검증 보너스: Vision+KIS 모두 매수면 +10\n\n■ 해석\n· 90+: 매우 강한 매수 신호 (복수 검증 + 높은 확신)\n· 80~89: 강한 매수 신호\n· 70~79: 관심 종목 (추가 확인 권장)\n\n■ 신호 검증 뱃지\n· ↑ 매수 유효: AI가 '매수' 판단 + 장중 가격이 상승 방향 → 분석과 시장 일치\n· ↓ 매도 유효: AI가 '매도' 판단 + 장중 가격이 하락 방향 → 분석과 시장 일치\n· 신호 약화: 분석 반대 방향 -2%~-5% → 주의\n· 신호 무효화: 분석 반대 방향 -5% 이상 → 신호 틀림\n· 중립 신호는 방향성이 없어 검증 뱃지를 표시하지 않습니다.\n\n■ 이중 검증 뱃지 (상세 팝업)\n· 고확신: Vision AI + KIS API 양쪽 모두 매수 일치\n· 확인필요: Vision AI만 매수, KIS API는 비매수\n· KIS매수: KIS API만 매수, Vision AI는 비매수\n· 혼조: 두 분석의 판단이 서로 상충",
  },
  simulation: {
    title: "전략 시뮬레이션",
    desc: "과거 AI 신호(vision)가 발행된 종목을 실제로 매매했다면 어땠을지 백테스트한 결과입니다.\n\n■ 매수 신호 → 5일 보유: '매수' 신호 종목을 5거래일 보유 후 매도한 성과\n■ 적극매수 → 5일 보유: '적극매수' 신호만 필터링. 건수는 적지만 평균수익이 높은 경향\n■ 손절 -3%: 보유 중 -3% 도달 시 즉시 매도. 승률은 낮아지나 큰 손실을 차단해 평균수익 개선\n\n· 승률 = 수익을 낸 매매 비율 (50% 이상이면 무작위보다 우위)\n· 평균수익 = 전체 매매의 평균 수익률\n\n활용법: ① 신호 신뢰도 판단 ② 적극매수 집중 vs 매수 분산 전략 선택 ③ 손절 기준 설정 참고. 단, 과거 성과이므로 시장 국면 변화에 따라 달라질 수 있습니다.",
  },
  pattern: {
    title: "차트 패턴 매칭",
    desc: "현재 종목의 차트 모양이 과거 어떤 종목의 어떤 시점과 비슷한지 찾아줍니다.\n\n■ 읽는 법 (예시)\n'03-11 삼성SDI 97%'\n→ 3월 11일의 삼성SDI 차트와 97% 유사\n\nD1~D5 = 그 과거 패턴 발생 후 1~5거래일 뒤 실제 등락률\n· D1 +0.0 → 1일 후 보합\n· D3 -4.3 → 3일 후 4.3% 하락\n· D5 +1.3 → 5일 후 1.3% 상승\n\n■ 해석\n· D1~D5가 대부분 +: 과거에 이 패턴 이후 상승한 경우가 많음 → 긍정적\n· D1~D5가 대부분 -: 과거에 이 패턴 이후 하락한 경우가 많음 → 부정적\n· 유사도 높을수록 (97%+) 참고 가치 높음\n\n■ 주의\n과거 패턴이 반복된다는 보장은 없습니다. 참고 지표로만 활용하세요.",
  },
  news: {
    title: "뉴스 임팩트",
    desc: "AI 분석 종목의 관련 뉴스를 카테고리별로 분류하고, 해당 종목의 당일 등락률을 함께 표시합니다.\n\n■ 카테고리\n· 이슈: 일반 시장 이슈 및 테마 뉴스\n· 수급: 외국인·기관 매매 관련 뉴스\n· 실적: 매출·영업이익 등 실적 관련\n· 종목뉴스: 개별 종목 재료·공시\n\n■ 표시 정보\n· 관심 뱃지: AI 매수 신호가 있는 종목의 뉴스\n· 등락률: 해당 종목의 당일 주가 변동률\n· 관심 종목 뉴스가 상단에 우선 표시됩니다\n\n뉴스를 클릭하면 해당 종목의 상세 분석을 확인할 수 있습니다.",
  },
  sector: {
    title: "테마별 자금 흐름",
    desc: "테마(섹터)별 외국인 투자자의 순매수/순매도 현황입니다. 양수(빨강)는 외국인이 사들이는 중, 음수(파랑)는 팔고 있는 중입니다. 자금 흐름의 방향으로 시장의 큰 그림을 파악합니다.",
  },
  sentiment: {
    title: "시장 심리 온도계",
    desc: "F&G, VIX, KOSPI 이격도, 외국인 수급 등 7개 지표를 종합한 시장 심리 스코어(0~100)입니다. 20 미만은 극단적 공포(역발상 매수 기회), 80 이상은 극단적 탐욕(이익 실현 검토)입니다.",
  },
  squeeze: {
    title: "공매도 역발상 시그널",
    desc: "공매도 비율이 높지만 펀더멘탈이 양호한 종목을 탐지합니다. 공매도 감소 + 거래량 증가 + 외국인 매수 전환 시 숏스퀴즈(급반등) 가능성이 높아집니다. 스코어가 높을수록 숏커버 가능성이 큽니다.",
  },
  valuation: {
    title: "밸류에이션 스크리너",
    desc: "PER(주가수익비율)이 낮고 저평가된 종목입니다. PER이 낮을수록 이익 대비 주가가 싸다는 의미입니다. PBR(주가순자산비율) 1 미만은 자산가치보다 주가가 낮은 상태입니다.",
  },
  divergence: {
    title: "거래량-가격 괴리",
    desc: "거래량과 가격이 반대로 움직이는 종목입니다. 거래량 급증 + 가격 하락은 매도 압력, 거래량 감소 + 가격 상승은 추세 약화 신호입니다. 괴리가 발생하면 추세 전환의 선행 지표가 될 수 있습니다.",
  },
  portfolio: {
    title: "내 포트폴리오",
    desc: "등록된 보유 종목의 비중, 매매 신호, 섹터 편중도를 분석합니다. 건강도(0~100)는 섹터 분산, 신호 일치도, 종목 수를 종합 평가합니다. 80 이상이면 양호, 50 미만이면 리밸런싱을 권장합니다.",
  },
  premarket: {
    title: "장전 프리마켓",
    desc: "장 시작 전 글로벌 시장 지표(F&G, VIX, 선물)를 종합하여 당일 시장 출발 방향을 예측합니다. 장 시작 전 투자 전략 수립에 참고합니다.",
  },
  supply_cluster: {
    title: "수급 클러스터",
    desc: "외국인/기관/개인 3주체의 매수·매도 조합으로 시장 국면을 7가지로 분류합니다. '외국인+기관 동반 매수'는 가장 강한 상승 신호, '3주체 동반 매도'는 가장 위험한 신호입니다.",
  },
  exit: {
    title: "손절/익절 최적화",
    desc: "종목의 변동성(ATR)을 기반으로 최적 손절(-%)과 익절(+%) 비율을 계산합니다. 변동성이 큰 종목은 넓은 손절폭, 안정적 종목은 좁은 손절폭을 권장합니다.",
  },
  events: {
    title: "이벤트 캘린더",
    desc: "FOMC, 옵션만기, 금통위 등 시장에 영향을 미치는 예정 이벤트를 보여줍니다. 복수 이벤트가 겹치면 변동성이 크게 확대될 수 있으므로 사전 대비가 필요합니다.",
  },
  propagation: {
    title: "테마 전이 예측",
    desc: "테마 대장주가 급등한 후 후발주로 매수세가 전이되는 패턴을 분석합니다. 대장주 급등 후 평균 15~30분 후 후발주가 따라 오르는 경향이 있습니다.",
  },
  program: {
    title: "프로그램 매매",
    desc: "기관의 차익거래(선물-현물 가격차 이용)와 비차익거래(포트폴리오 리밸런싱) 현황입니다. 프로그램 순매수 전환은 기관 자금 유입, 순매도 전환은 유출을 의미합니다.",
  },
  heatmap: {
    title: "시간대별 수익률",
    desc: "장중 시간대별 평균 수익률 패턴입니다. 특정 시간대에 반복적으로 강하거나 약한 패턴이 있으면 매매 타이밍 참고가 됩니다. 9시(장초반)와 14시30분(장마감 전)에 변동성이 큰 경향이 있습니다.",
  },
  insider: {
    title: "내부자 거래",
    desc: "DART 공시 기반 대주주/임원의 자사주 매수·매도 내역입니다. 내부자 매수는 회사 전망에 대한 자신감, 매도는 현금화 필요 또는 부정적 전망을 시사할 수 있습니다.",
  },
  consensus: {
    title: "컨센서스 괴리",
    desc: "증권사 목표가가 조용히 상향 또는 하향 조정되는 '드리프트'를 감지합니다. 다수 증권사가 동시에 목표가를 올리면 실적 기대감, 내리면 실적 하향 조정을 의미합니다.",
  },
  auction: {
    title: "동시호가 분석",
    desc: "장 시작(08:30~09:00)과 마감(15:20~15:30) 동시호가 시간대의 주문 패턴입니다. 동시호가에 대량 주문이 집중되면 기관의 방향성 베팅 신호일 수 있습니다.",
  },
  orderbook: {
    title: "호가창 압력",
    desc: "매수 호가 물량 vs 매도 호가 물량의 비율로 단기 가격 방향을 추정합니다. 매수벽이 두꺼우면 하방 지지, 매도벽이 두꺼우면 상방 저항을 의미합니다.",
  },
  mentor: {
    title: "AI 투자 멘토",
    desc: "매매 이력을 분석하여 반복되는 투자 습관과 편향을 감지하고, AI가 개선 방안을 코칭합니다. 추격매수, 손절 회피, 섹터 편중 등의 패턴을 객관적으로 진단합니다.",
  },
  journal: {
    title: "매매 일지",
    desc: "매매 기록을 자동으로 일지화하고, 매수/매도 시점의 시장 상황(신호, 테마, 수급)을 매칭하여 회고합니다. 보류 중인 기능입니다.",
  },
  correlation: {
    title: "상관관계 네트워크",
    desc: "종목 간 주가 상관관계를 분석합니다. 상관계수 0.8 이상이면 같이 오르내리는 경향이 강해 분산 효과가 낮습니다. 포트폴리오 구성 시 참고합니다.",
  },
  earnings: {
    title: "실적 프리뷰",
    desc: "실적 발표 예정 종목의 사전 수급 변화를 추적합니다. 발표 전 외국인/기관 매수가 급증하면 서프라이즈 가능성, 매도가 늘면 미스 가능성을 시사합니다.",
  },
  member: {
    title: "증권사 매매 동향",
    desc: "종목별 증권사(회원사)의 매수/매도 상위 5개사와 외국인 순매수 현황입니다. 특정 증권사가 집중 매수하면 기관 자금 유입 신호일 수 있습니다.",
  },
  trading_value: {
    title: "거래대금 TOP",
    desc: "당일 거래대금이 가장 많은 종목 순위입니다. 거래대금이 큰 종목은 시장의 관심이 집중된 종목이며, 유동성이 풍부하여 매매가 용이합니다.",
  },
  paper_trading: {
    title: "모의투자 현황",
    desc: "AI 신호 기반 모의투자(Paper Trading) 결과입니다. 실제 매매 없이 AI 신호대로 매매했을 때의 성과를 추적하여 신호의 유효성을 검증합니다.",
  },
  forecast: {
    title: "예측 적중률",
    desc: "AI 테마 예측의 과거 적중률입니다. 상단 뱃지는 테마 대분류별 누적 적중률로, 초록(≥70%)은 높은 신뢰도, 주황(≥40%)은 보통, 빨강(<40%)은 낮은 신뢰도입니다. 적중률이 높은 테마의 예측은 투자 참고 가치가 높고, 낮은 테마는 주의가 필요합니다. 하단은 일별 합산 결과입니다.",
  },
  volume_profile: {
    title: "매물대 지지/저항",
    desc: "현재가가 매물대 지지선/저항선 근처에 있는 종목만 표시합니다. '지지대 근접'은 매수 기회, '저항대 근접'은 돌파 또는 반락 주의, '지지 이탈'은 손절 검토, '저항 돌파'는 추세 전환 신호입니다. 괴리율은 현재가 대비 지지/저항선까지의 거리(%)입니다.",
  },
  consistency: {
    title: "신호 변동 모니터",
    desc: "최근 5일 내 시그널이 변경된 종목만 표시합니다. '매수 전환'은 직전 중립/매도에서 매수로, '매도 전환'은 매수/중립에서 매도로 바뀐 종목입니다. '매수→중립'/'매도→중립'은 신호가 해제된 종목, '신호 변동'은 과거 5일 내 변동이 있었으나 현재 중립인 종목입니다.",
  },
  intraday_flow: {
    title: "장중 종목별 수급",
    desc: "장중 가집계(09:31~14:31) 시점의 종목별 외국인/기관/개인 실시간 순매수 현황입니다. 장마감 확정 데이터와 달리 장중 자금 흐름을 실시간으로 추적합니다.",
  },
};

/* 색상 키워드 → 실제 색상 매핑 */
const COLOR_MAP: Record<string, string> = {
  "초록": "#22c55e", "녹색": "#22c55e", "빨강": "#ef4444", "빨간": "#ef4444",
  "주황": "#f97316", "파랑": "#3b82f6", "파란": "#3b82f6", "노랑": "#eab308",
};
const COLOR_RE = new RegExp(`(${Object.keys(COLOR_MAP).join("|")})`, "g");

/** desc 문자열을 구조화된 JSX로 변환 */
function renderHelpDesc(desc: string) {
  const paragraphs = desc.split("\n\n");
  return paragraphs.map((para, pi) => {
    const lines = para.split("\n");
    const elements: React.ReactNode[] = [];
    let bullets: string[] = [];

    const flushBullets = () => {
      if (bullets.length === 0) return;
      elements.push(
        <ul key={`b-${pi}-${elements.length}`} className="space-y-1 ml-1">
          {bullets.map((b, bi) => (
            <li key={bi} className="flex gap-1.5 text-sm t-text-sub leading-relaxed">
              <span className="t-text-dim shrink-0">·</span>
              <span>{colorize(b)}</span>
            </li>
          ))}
        </ul>
      );
      bullets = [];
    };

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("■")) {
        flushBullets();
        elements.push(
          <h4 key={`h-${pi}-${elements.length}`} className="text-[13px] font-semibold t-text mt-3 mb-1">
            {trimmed.replace(/^■\s*/, "")}
          </h4>
        );
      } else if (trimmed.startsWith("·")) {
        bullets.push(trimmed.replace(/^·\s*/, ""));
      } else if (trimmed) {
        flushBullets();
        elements.push(
          <p key={`p-${pi}-${elements.length}`} className="text-sm t-text-sub leading-relaxed">
            {colorize(trimmed)}
          </p>
        );
      }
    }
    flushBullets();
    return <div key={pi} className={pi > 0 ? "mt-3" : ""}>{elements}</div>;
  });
}

/** 색상 키워드 앞에 컬러 칩(●) 삽입 */
function colorize(text: string): React.ReactNode {
  const parts = text.split(COLOR_RE);
  if (parts.length === 1) return text;
  return parts.map((part, i) => {
    const color = COLOR_MAP[part];
    if (color) {
      return (
        <span key={i} className="inline-flex items-center gap-0.5">
          <span className="inline-block w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
          <span>{part}</span>
        </span>
      );
    }
    return part;
  });
}

export function SectionHeader({
  id,
  children,
  count,
  timestamp,
}: {
  id: string;
  children: React.ReactNode;
  count?: number;
  timestamp?: string;
}) {
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; arrowLeft: number } | null>(null);
  const help = SECTION_HELP[id];

  const updatePos = useCallback(() => {
    if (!btnRef.current) return;
    const r = btnRef.current.getBoundingClientRect();
    const popW = Math.min(340, window.innerWidth - 24);
    // 팝오버를 아이콘 아래 중앙 정렬, 화면 밖 나가지 않도록 clamp
    let left = r.left + r.width / 2 - popW / 2;
    left = Math.max(12, Math.min(left, window.innerWidth - popW - 12));
    const arrowLeft = r.left + r.width / 2 - left;
    setPos({ top: r.bottom + 8, left, arrowLeft });
  }, []);

  const handleOpen = () => {
    updatePos();
    setOpen(true);
  };

  // 외부 클릭 닫기
  useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node) &&
          btnRef.current && !btnRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onScroll = () => updatePos();
    document.addEventListener("mousedown", onClickOutside);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, updatePos]);

  return (
    <>
      <div id={id} className="flex items-center gap-2 mb-3 scroll-mt-24">
        <h2 className="text-base font-semibold t-text shrink-0">
          {children}
          {count != null && (
            <span className="text-sm font-normal t-text-dim ml-1">
              ({count})
            </span>
          )}
        </h2>
        {help && (
          <button
            ref={btnRef}
            onClick={() => open ? setOpen(false) : handleOpen()}
            className="t-text-dim hover:text-blue-500 transition"
          >
            <HelpCircle size={16} />
          </button>
        )}
        {timestamp && (
          <span className="ml-auto text-[11px] t-text-sub shrink-0">{timestamp}</span>
        )}
      </div>
      {open && help && pos && createPortal(
        <div
          ref={popRef}
          className="fixed z-[9999] anim-scale-in"
          style={{ top: pos.top, left: pos.left, width: Math.min(340, window.innerWidth - 24) }}
        >
          {/* 화살표 */}
          <div
            className="absolute -top-[6px] w-3 h-3 rotate-45 t-card border-l border-t t-border-light"
            style={{ left: pos.arrowLeft - 6 }}
          />
          <div className="t-card rounded-xl shadow-lg border t-border-light max-h-[60vh] flex flex-col overflow-hidden">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-4 pt-3 pb-2 shrink-0">
              <h3 className="text-[13px] font-semibold t-text">{help.title}</h3>
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 -mr-1.5 t-text-dim hover:t-text-sub transition rounded-lg"
                aria-label="닫기"
              >
                <X size={16} />
              </button>
            </div>
            <div className="overflow-y-auto px-4 pb-4">
              {renderHelpDesc(help.desc)}
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
