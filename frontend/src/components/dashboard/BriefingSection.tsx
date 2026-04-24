import { Globe, Flame, Target, AlertTriangle, Lightbulb, Pin } from "lucide-react";
import { SectionHeader } from "../HelpDialog";

function Badge({ children, variant = "default" }: { children: React.ReactNode; variant?: string }) {
  const cls: Record<string, string> = {
    danger: "bg-red-500/10 text-red-400 border-red-500/20",
    warning: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    success: "bg-green-500/10 text-green-400 border-green-500/20",
    blue: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    purple: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    default: "t-muted t-text-sub border-transparent",
  };
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full border whitespace-nowrap ${cls[variant] || cls.default}`}>
      {children}
    </span>
  );
}

export default function BriefingSection({ briefing, performance, crossSignal, smartMoney, anomalies, riskMonitor, allStockList, briefTs, setStockDetail, setConfExp }: {
  briefing: any;
  performance: any;
  crossSignal: any;
  smartMoney: any;
  anomalies?: any;
  riskMonitor?: any;
  allStockList?: any[];
  briefTs: string;
  setStockDetail: (v: any) => void;
  setConfExp: (v: any) => void;
}) {
  const raw = briefing.morning as string;
  // HTML 태그 정리
  const strip = (s: string) => s.replace(/<\/?[bi]>/g, "").replace(/<br\s*\/?>/gi, "\n").replace(/&nbsp;/g, " ").trim();
  // 섹션명 앵커 기반 파서 — 래퍼 태그/숫자/콜론 변형에 독립적
  // Gemini 형식이 바뀌어도 알려진 섹션명만 정확히 나오면 작동
  const KNOWN_SECTIONS = ["글로벌 환경", "오늘의 주목 테마", "고확신 종목", "주목 종목", "주의 종목", "전략 제안"];
  const normalized = raw
    .replace(/<\/?(?:b|i)\s*>/gi, "")
    .replace(/<\/?font[^>]*>/gi, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/\*\*/g, "")
    .replace(/&nbsp;/g, " ");
  const anchorRegex = new RegExp(
    `(?:^|\\n)[\\s]*(?:\\d+\\.\\s*)?(${KNOWN_SECTIONS.join("|")})\\s*:?\\s*(?=\\n|$)`,
    "g",
  );
  const anchors = [...normalized.matchAll(anchorRegex)];
  let sections: { title: string; body: string }[] = [];
  if (anchors.length >= 2) {
    for (let i = 0; i < anchors.length; i++) {
      const title = anchors[i][1];
      const start = anchors[i].index! + anchors[i][0].length;
      const end = i < anchors.length - 1 ? anchors[i + 1].index! : normalized.length;
      const body = normalized.slice(start, end).trim();
      sections.push({ title, body });
    }
  } else {
    // 파싱 실패 — 개발자가 즉시 인지할 수 있도록 경고 출력
    // eslint-disable-next-line no-console
    console.warn("[BriefingSection] 섹션 파싱 실패. 원문 처음 300자:", raw.slice(0, 300));
    sections = [{ title: "AI 분석", body: strip(raw) }];
  }
  // "주목 테마" 섹션은 테마 예측 카드에 통합 → AI 브리핑에서 제거
  const hasThemeForecast = performance?.theme_forecast?.themes?.length > 0;
  if (hasThemeForecast) {
    sections = sections.filter(sec => {
      const t = sec.title;
      return !(t.includes("테마") && (t.includes("주목") || t.includes("주요")));
    });
  }
  // "주목 테마" 섹션의 촉매 설명을 추출 (테마 예측 카드에서 활용)
  const themeCatalystMap: Record<string, string> = {};
  const origThemeSec = raw.match(/\d+\.\s*<b>[^<]*주목[^<]*<\/b>([\s\S]*?)(?=\d+\.\s*<b>|$)/);
  if (origThemeSec) {
    const lines = origThemeSec[1].replace(/<\/?[bi]>/g, "").split("\n").filter((l: string) => l.trim());
    for (const line of lines) {
      const m = line.match(/[✔️✅·\-\*]\s*(.+?)\s*\((.+)\)/);
      if (m) themeCatalystMap[m[1].trim()] = m[2].trim();
    }
  }
  const matchKey = (title: string) => {
    if (title.includes("글로벌") || title.includes("환경") || title.includes("시장")) return "글로벌 환경";
    if (title.includes("테마") && (title.includes("주목") || title.includes("주요"))) return "오늘의 주목 테마";
    if (title.includes("주목") && title.includes("주의")) return "주목 종목";  // "주목/주의 종목"
    if (title.includes("핵심") || title.includes("고확신") || title.includes("쌍방") || title.includes("관심") || (title.includes("주목") && title.includes("종목"))) return "주목 종목";
    if (title.includes("주의") || title.includes("위험")) return "주의 종목";
    if (title.includes("전략") || title.includes("제안") || title.includes("투자 전략")) return "전략 제안";
    return title;
  };
  const iconMap: Record<string, React.ReactNode> = {
    "글로벌 환경": <Globe size={16} />, "오늘의 주목 테마": <Flame size={16} />, "고확신 종목": <Target size={16} />,
    "주목 종목": <Target size={16} />, "주의 종목": <AlertTriangle size={16} />, "전략 제안": <Lightbulb size={16} />,
  };
  const accentMap: Record<string, string> = {
    "글로벌 환경": "border-l-slate-400", "오늘의 주목 테마": "border-l-cyan-400",
    "고확신 종목": "border-l-emerald-400", "주목 종목": "border-l-emerald-400", "주의 종목": "border-l-rose-400", "전략 제안": "border-l-indigo-400",
  };
  // 종목명(코드) 패턴을 클릭 가능한 요소로 변환
  const allStockData = [...(crossSignal || []), ...(smartMoney || []), ...(anomalies || []), ...(riskMonitor || []), ...(allStockList || [])];
  // 종목명→데이터 매핑 (이름 기반 매칭용)
  const stockByName: Record<string, any> = {};
  for (const s of allStockData) {
    if (s?.name) stockByName[s.name] = s;
  }
  const renderTextWithStockLinks = (text: string) => {
    const cleaned = text.replace(/<[^>]+>/g, "");
    // 1차: "종목명(6자리코드)" 패턴
    // 2차: "종목명 (매수)" 또는 "종목명:" 패턴 (브리핑 텍스트)
    // 영문 대문자만 3~4글자(ETF/외국주식 약어)는 오탐 가능성 높으므로 제외
    const stockNames = Object.keys(stockByName).filter(n => n.length >= 2 && !/^[A-Z]{2,4}$/.test(n)).sort((a, b) => b.length - a.length);
    if (!stockNames.length) return <>{cleaned}</>;
    const namePattern = stockNames.map(n => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
    const regex = new RegExp(`(${namePattern})`, "g");
    const parts = cleaned.split(regex);
    return parts.map((part, k) => {
      const detail = stockByName[part];
      if (detail) {
        return (
          <span key={k}
            onClick={(e) => { e.stopPropagation(); setStockDetail(detail); }}
            className="font-semibold text-blue-400 cursor-pointer hover:underline"
          >{part}</span>
        );
      }
      return <span key={k}>{part}</span>;
    });
  };
  // 본문 라인 렌더링
  const renderBody = (body: string) => {
    return body.split("\n").filter(l => l.trim()).map((line: string, j: number) => {
      let trimmed = line.trim();
      // 잔여 번호 제거 ("2.", "3." 등 단독 라인 또는 앞쪽 번호)
      if (/^\d+\.\s*$/.test(trimmed)) return null;
      trimmed = trimmed.replace(/^\d+\.\s*/, "");
      // 앞쪽 콜론 제거 (": 설명" → "설명")
      trimmed = trimmed.replace(/^:\s*/, "");
      if (!trimmed) return null;
      // 체크 항목 (✔️, ✅, ·, -, *)
      if (/^[✔️✅·\-\*]/.test(trimmed)) {
        const text = trimmed.replace(/^[✔️✅·\-\*]+\s*/, "");
        if (!text) return null;
        return (
          <div key={j} className="flex items-start gap-2 py-0.5">
            <span className="text-emerald-400 mt-0.5 text-[10px]">●</span>
            <span className="t-text-sub text-[13px] leading-relaxed">{renderTextWithStockLinks(text)}</span>
          </div>
        );
      }
      // 주의/전략 라벨 제거
      const cleaned = trimmed.replace(/^(주의 종목:|전략 제안:)\s*/i, "");
      return <p key={j} className="t-text text-[13px] leading-[1.7]">{renderTextWithStockLinks(cleaned)}</p>;
    }).filter(Boolean);
  };
  return (
    <section className="space-y-3">
      <SectionHeader id="briefing" timestamp={briefTs}>AI 모닝 브리핑</SectionHeader>
      <div className="rounded-xl border t-border-light t-card-alt p-4 space-y-4">
        {sections.map((sec: any, i: number) => {
          const key = matchKey(sec.title);
          return (
          <div key={i} className={i > 0 ? "pt-3 border-t t-border-light" : ""}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-base ${accentMap[key]?.replace("border-l-", "text-") || "t-text-dim"}`}>{iconMap[key] || <Pin size={16} />}</span>
              <span className={`text-[14px] font-bold tracking-tight ${accentMap[key]?.replace("border-l-", "text-") || "t-text"}`}>{sec.title}</span>
            </div>
            <div className="space-y-1 pl-6">
              {renderBody(sec.body).length > 0
                ? renderBody(sec.body)
                : <p className="text-[12px] t-text-dim italic">해당 항목 없음</p>
              }
            </div>
          </div>
          );
        })}
      </div>
      {/* 오늘의 테마 예측 — AI 브리핑 주목 테마 통합 */}
      {performance?.theme_forecast?.themes?.length > 0 && (
        <div className="rounded-xl border t-border-light border-l-[3px] border-l-cyan-400/60 t-card-alt p-4">
          <div className="flex items-center gap-2 mb-2.5">
            <Flame size={16} />
            <span className="text-[13px] font-bold t-text tracking-tight">오늘의 주목 테마</span>
          </div>
          {performance.theme_forecast.market_context && (
            <p className="text-[13px] t-text-sub leading-[1.7] mb-3">
              {performance.theme_forecast.market_context}
            </p>
          )}
          <div className="space-y-0">
            {performance.theme_forecast.themes.slice(0, 5).map((t: any, i: number) => {
              const themeName = t.theme_name || t.name || "";
              const conf = t.confidence;
              const confLabel = typeof conf === "number" ? `${conf}%` : conf || "";
              const isHigh = confLabel.includes("높") || (typeof conf === "number" && conf >= 70);
              const isMid = confLabel.includes("보통") || (typeof conf === "number" && conf >= 40 && conf < 70);
              // 촉매: theme_forecast 원본 우선, AI 브리핑 파싱 폴백
              const catalyst = t.catalyst || Object.entries(themeCatalystMap).find(([k]) => themeName.includes(k) || k.includes(themeName))?.[1] || "";
              const description = t.description || "";
              const leaders = (t.leader_stocks || []).slice(0, 3);
              return (
                <div key={i} className="py-2.5 border-b t-border-light last:border-b-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-medium t-text">{themeName}</span>
                    {confLabel && (
                      <span onClick={() => setConfExp({ theme: themeName, confidence: confLabel, catalyst, description } as any)}
                        className={`text-[11px] font-semibold px-2 py-0.5 rounded-full shrink-0 cursor-pointer ${
                        isHigh ? "bg-emerald-500/10 text-emerald-500" :
                        isMid ? "bg-amber-500/10 text-amber-500" :
                        "bg-gray-500/10 t-text-dim"
                      }`}>{confLabel}</span>
                    )}
                  </div>
                  {(catalyst || leaders.length > 0) && (
                    <div className="mt-1.5 space-y-1">
                      {catalyst && <div className="text-[12px] t-text-sub leading-relaxed">{catalyst}</div>}
                      {leaders.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {leaders.map((l: any, li: number) => {
                            const detail = [...(crossSignal || []), ...(smartMoney || [])].find((s: any) => s.code === l.code);
                            return (
                              <span key={li}
                                onClick={(e) => { e.stopPropagation(); detail ? setStockDetail(detail) : setStockDetail({ name: l.name, code: l.code, _noData: true }); }}
                                className="text-[11px] px-1.5 py-0.5 rounded bg-blue-500/8 t-text-sub cursor-pointer hover:bg-blue-500/20 transition-colors"
                              >{l.name}</span>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
