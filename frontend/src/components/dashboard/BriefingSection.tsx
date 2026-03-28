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

export default function BriefingSection({ briefing, performance, crossSignal, smartMoney, briefTs, setStockDetail, setConfExp }: {
  briefing: any;
  performance: any;
  crossSignal: any;
  smartMoney: any;
  briefTs: string;
  setStockDetail: (v: any) => void;
  setConfExp: (v: any) => void;
}) {
  const raw = briefing.morning as string;
  // HTML 태그 정리
  const strip = (s: string) => s.replace(/<\/?[bi]>/g, "").replace(/<br\s*\/?>/gi, "\n").replace(/&nbsp;/g, " ").trim();
  // 범용 섹션 파서: Gemini 형식 변동에 대응
  let sections: { title: string; body: string }[] = [];
  // 모든 가능한 제목 패턴을 순서대로 시도
  const patterns = [
    // 1) 줄바꿈 + "<b>N. 제목</b>" — 최상위 섹션만 (서브 항목 제외)
    /\n\s*<b>(\d+\.\s*[^<\n]{2,30}?)\s*<\/b>/g,
    // 2) "**N. 제목**"
    /\*\*(\d+\.\s*[^*\n]{2,30}?)\*\*/g,
  ];
  for (const regex of patterns) {
    if (sections.length >= 2) break;
    sections = [];
    const matches = [...raw.matchAll(regex)];
    // 첫 매칭이 날짜/타이틀이면 건너뛰기
    const filtered = matches.filter(m => {
      const t = strip(m[1]);
      return t && t.length >= 2 && t.length <= 30 && !t.includes("모닝") && !t.includes("브리프") && !t.includes("년 ");
    });
    if (filtered.length >= 2) {
      for (let i = 0; i < filtered.length; i++) {
        const title = strip(filtered[i][1]).replace(/:$/, "").replace(/^\d+\.\s*/, "");
        const start = filtered[i].index! + filtered[i][0].length;
        const end = i < filtered.length - 1 ? filtered[i + 1].index! : raw.length;
        const body = strip(raw.slice(start, end)).replace(/\n\d+\.\s*$/, "").replace(/^\d+\.\s*/, "");
        if (title) sections.push({ title, body });
      }
    }
  }
  // 최종 폴백
  if (sections.length < 2) {
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
    if (title.includes("핵심") || title.includes("고확신") || title.includes("쌍방") || title.includes("관심") || title.includes("종목")) return "주목 종목";
    if (title.includes("주의") || title.includes("위험")) return "주의 종목";
    if (title.includes("전략") || title.includes("제안")) return "전략 제안";
    return title;
  };
  const iconMap: Record<string, React.ReactNode> = {
    "글로벌 환경": <Globe size={16} />, "오늘의 주목 테마": <Flame size={16} />, "고확신 종목": <Target size={16} />,
    "주의 종목": <AlertTriangle size={16} />, "전략 제안": <Lightbulb size={16} />,
  };
  const accentMap: Record<string, string> = {
    "글로벌 환경": "border-l-slate-400", "오늘의 주목 테마": "border-l-cyan-400",
    "고확신 종목": "border-l-emerald-400", "주의 종목": "border-l-rose-400", "전략 제안": "border-l-indigo-400",
  };
  // 종목명(코드) 패턴을 클릭 가능한 요소로 변환
  const allStockData = [...(crossSignal || []), ...(smartMoney || [])];
  const renderTextWithStockLinks = (text: string) => {
    // HTML 태그 제거 (briefing 데이터에 <font> 등 포함 가능)
    const cleaned = text.replace(/<[^>]+>/g, "");
    // "종목명(6자리코드)" 패턴 매칭
    const parts = cleaned.split(/([가-힣A-Za-z\s]+\(\d{6}\))/g);
    return parts.map((part, k) => {
      const m = part.match(/^(.+)\((\d{6})\)$/);
      if (m) {
        const name = m[1].trim();
        const code = m[2];
        const detail = allStockData.find((s: any) => s.code === code);
        return (
          <span key={k}
            onClick={() => detail ? setStockDetail(detail) : setStockDetail({ name, code, _noData: true })}
            className="font-semibold text-blue-400 cursor-pointer hover:underline"
          >{name}({code})</span>
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
      {sections.map((sec: any, i: number) => {
        const key = matchKey(sec.title);
        return (
        <div key={i} className={`rounded-xl border t-border-light border-l-[3px] ${accentMap[key] || "border-l-gray-400"} t-card-alt p-4`}>
          <div className="flex items-center gap-2 mb-2.5">
            <span className="text-base">{iconMap[key] || <Pin size={16} />}</span>
            <span className="text-[13px] font-bold t-text tracking-tight">{sec.title}</span>
          </div>
          <div className="space-y-1">
            {renderBody(sec.body).length > 0
              ? renderBody(sec.body)
              : <p className="text-[12px] t-text-dim italic">해당 항목 없음</p>
            }
          </div>
        </div>
        );
      })}
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
