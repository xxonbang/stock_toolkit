import { useState } from "react";
import { HelpCircle, X } from "lucide-react";

export const SECTION_HELP: Record<string, { title: string; desc: string }> = {
  briefing: {
    title: "AI 모닝 브리프",
    desc: "Gemini AI가 시장 데이터를 종합 분석하여 매일 아침 작성하는 투자 브리핑입니다. 글로벌 환경, 주목 테마, 고확신 종목, 전략 제안을 포함합니다.",
  },
  market: {
    title: "시장 현황",
    desc: "공포·탐욕 지수(Fear & Greed)는 시장 심리를 0~100으로 측정합니다. 25 미만은 극단적 공포(매수 기회), 75 이상은 극단적 탐욕(과열 주의)입니다. VIX는 변동성 지수로, 20 이상이면 불안정한 시장을 의미합니다.",
  },
  signals: {
    title: "신호 분포",
    desc: "분석 대상 전체 종목의 매매 신호를 5단계로 분류한 결과입니다. 적극매수/매수가 많으면 시장이 긍정적, 매도/적극매도가 많으면 부정적 흐름입니다.",
  },
  cross: {
    title: "교차 신호",
    desc: "테마 분석(대장주)과 기술적 분석(매수 신호)이 동시에 일치하는 종목입니다. 두 독립 시스템의 합의이므로 단일 신호보다 신뢰도가 높습니다. 신뢰도는 AI 분석의 확신 정도(0~100%)입니다.",
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
    desc: "매도 신호, 외국인 대량 매도 등 복수 위험 요인이 동시에 발생한 종목입니다. '높음'은 2개 이상, '주의'는 1개 위험 요인이 감지된 상태입니다.",
  },
  smartmoney: {
    title: "스마트 머니 TOP",
    desc: "외국인·기관 투자자의 매수 패턴을 종합 평가한 스코어입니다. 매수 신호 + 외국인 순매수 + AI 신뢰도를 가중 합산합니다. 90 이상이면 강한 기관 매수 흐름을 의미합니다.",
  },
  simulation: {
    title: "전략 시뮬레이션",
    desc: "과거 데이터에 특정 매매 전략을 적용했을 때의 성과입니다. 승률은 수익을 낸 매매의 비율, 평균 수익은 전체 매매의 평균 수익률입니다. hold=보유일수, stop=손절 기준입니다.",
  },
  pattern: {
    title: "차트 패턴 매칭",
    desc: "현재 차트 패턴과 과거에 유사했던 패턴을 코사인 유사도로 비교합니다. D+5는 유사 패턴 발생 후 5거래일 뒤의 실제 수익률입니다. 유사도가 높을수록 패턴이 비슷합니다.",
  },
  news: {
    title: "뉴스 임팩트",
    desc: "종목 관련 뉴스를 카테고리별로 분류하고, 해당 뉴스가 주가에 미친 영향을 분석합니다. 실적·정책·수급 등 유형별로 과거 평균 임팩트를 참고할 수 있습니다.",
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
  gap: {
    title: "갭 분석",
    desc: "전일 종가 대비 시가가 크게 벌어진(갭) 종목입니다. 갭 상승은 호재 반영, 갭 하락은 악재 반영입니다. 갭 메꿈 확률은 과거 유사 갭이 이후 메워진 비율입니다.",
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
};

export function SectionHeader({
  id,
  children,
  count,
}: {
  id: string;
  children: React.ReactNode;
  count?: number;
}) {
  const [open, setOpen] = useState(false);
  const help = SECTION_HELP[id];

  return (
    <>
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-base font-semibold text-gray-900">
          {children}
          {count != null && (
            <span className="text-sm font-normal text-gray-400 ml-1">
              ({count})
            </span>
          )}
        </h2>
        {help && (
          <button
            onClick={() => setOpen(true)}
            className="text-gray-400 hover:text-blue-500 transition"
          >
            <HelpCircle size={16} />
          </button>
        )}
      </div>
      {open && help && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-white rounded-xl shadow-xl max-w-sm w-full p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-3">
              <h3 className="font-semibold text-gray-900">{help.title}</h3>
              <button
                onClick={() => setOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X size={18} />
              </button>
            </div>
            <p className="text-sm text-gray-600 leading-relaxed">{help.desc}</p>
          </div>
        </div>
      )}
    </>
  );
}
