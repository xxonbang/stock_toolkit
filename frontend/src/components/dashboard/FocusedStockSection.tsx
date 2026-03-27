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

function Empty({ text = "현재 해당 데이터 없음" }: { text?: string }) {
  return (
    <div className="text-center py-5">
      <div className="t-text-dim text-lg mb-1">—</div>
      <div className="text-xs t-text-dim">{text}</div>
      <div className="text-[10px] t-text-dim mt-0.5">데이터 갱신 후 표시됩니다</div>
    </div>
  );
}

export default function FocusedStockSection({ performance, crossSignal, smartMoney, consecutiveSignals, ts, setStockDetail }: {
  performance: any;
  crossSignal: any;
  smartMoney: any;
  consecutiveSignals: any;
  ts: string;
  setStockDetail: (v: any) => void;
}) {
  const c = performance.by_source.combined;
  const total = c.total || 0;

  // 교차 신호 코드 셋 + 연속 신호 맵
  const crossCodeSet = new Set((crossSignal || []).map((s: any) => s.code));
  const streakMap: Record<string, number> = {};
  for (const r of (consecutiveSignals?.and_condition || [])) if (r.code) streakMap[r.code] = r.streak;
  for (const r of (consecutiveSignals?.or_condition || [])) if (r.code && !streakMap[r.code]) streakMap[r.code] = r.streak;

  // 수급 맵 (smartMoney)
  const supplyMap: Record<string, number> = {};
  for (const sm of (smartMoney || [])) if (sm?.code) supplyMap[sm.code] = sm.foreign_net || 0;

  // 매수 종목 수집 + 카테고리 분류
  const seen = new Set<string>();
  const allBuy: { s: any; cat: string; score: number }[] = [];

  const classify = (s: any) => {
    const buys = new Set(["매수", "적극매수"]);
    const hasVision = buys.has(s.vision_signal || "");
    const hasApi = buys.has(s.api_signal || "");
    const isCross = crossCodeSet.has(s.code);
    if (hasVision && hasApi && isCross) return "고확신";
    if (isCross) return "대장주";
    if (hasVision && hasApi) return "매수 일치";
    return "매수";
  };

  const catOrder: Record<string, number> = { "고확신": 0, "대장주": 1, "매수 일치": 2, "매수": 3 };

  (crossSignal || []).forEach((s: any) => {
    if (!seen.has(s.code)) {
      const cat = classify(s);
      allBuy.push({ s, cat, score: (s.confidence || 0) * 100 });
      seen.add(s.code);
    }
  });
  (smartMoney || []).forEach((s: any) => {
    if (seen.has(s.code)) return;
    const buys = new Set(["매수", "적극매수"]);
    const hasVision = buys.has(s.vision_signal || "");
    const hasApi = buys.has(s.api_signal || "");
    // vision 또는 api 중 하나라도 매수 신호가 있어야 포함
    if (hasVision || hasApi) {
      allBuy.push({ s, cat: classify(s), score: s.smart_money_score || 0 });
      seen.add(s.code);
    }
  });

  allBuy.sort((a, b) => (catOrder[a.cat] ?? 9) - (catOrder[b.cat] ?? 9) || b.score - a.score);

  const catStyle: Record<string, { bg: string; text: string; border: string }> = {
    "고확신": { bg: "t-card-alt", text: "text-red-500", border: "border-l-[3px] border-l-red-500 border t-border-light" },
    "대장주": { bg: "t-card-alt", text: "text-orange-500", border: "border-l-[3px] border-l-orange-400 border t-border-light" },
    "매수 일치": { bg: "t-card-alt", text: "text-blue-500", border: "border-l-[3px] border-l-blue-400 border t-border-light" },
    "매수": { bg: "t-card-alt", text: "t-text", border: "border t-border-light" },
  };

  // 카테고리별 그룹핑
  const groups: Record<string, typeof allBuy> = {};
  for (const item of allBuy) {
    (groups[item.cat] ??= []).push(item);
  }

  return (
    <section className="t-card rounded-xl p-4">
      <SectionHeader id="signals" timestamp={ts}>AI 주목 종목</SectionHeader>
      <div className="text-xs t-text-sub mb-3">
        AI 분석 {total}종목 중 <span className="text-red-500 font-semibold">매수 신호 {allBuy.length}종목</span>
      </div>
      {["고확신", "대장주", "매수 일치", "매수"].map(cat => {
        const items = groups[cat];
        if (!items?.length) return null;
        const style = catStyle[cat];
        return (
          <div key={cat} className="mb-2.5">
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-md ${
                cat === "고확신" ? "bg-red-500/10 text-red-400" :
                cat === "대장주" ? "bg-orange-500/10 text-orange-400" :
                cat === "매수 일치" ? "bg-blue-500/10 text-blue-400" :
                "t-card-alt t-text-sub"
              }`}>{cat}</span>
              <span className="text-[10px] t-text-dim">{items.length}종목</span>
            </div>
            <div className="space-y-1">
              {items.map(({ s }, i) => {
                const streak = streakMap[s.code];
                const foreignNet = supplyMap[s.code];
                const intra = s.intraday || {};
                return (
                  <div key={i} onClick={() => setStockDetail(s)}
                    className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg border cursor-pointer card-hover ${style.bg} ${style.border}`}>
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className={`text-[13px] font-medium truncate ${style.text}`}>{s.name}</span>
                      {streak && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-500 font-medium">{streak}일 연속</span>}
                      {foreignNet != null && foreignNet !== 0 && (
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${foreignNet > 0 ? "bg-red-500/10 text-red-500" : "bg-blue-500/10 text-blue-500"}`}>
                          외인{foreignNet > 0 ? "↑" : "↓"}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0 text-[10px] t-text-dim">
                      {s.theme && <span className="truncate max-w-[80px]">{s.theme}</span>}
                      {intra.change_rate != null && intra.change_rate !== 0 && (
                        <span className={intra.change_rate >= 0 ? "text-red-400 font-medium" : "text-blue-400 font-medium"}>
                          {intra.change_rate >= 0 ? "+" : ""}{intra.change_rate}%
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
      {allBuy.length === 0 && <Empty text="현재 매수 신호 종목 없음" />}
    </section>
  );
}
