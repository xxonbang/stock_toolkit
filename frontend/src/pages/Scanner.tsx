import { useEffect, useState } from "react";
import { Search, RotateCcw, Filter, Sun, Moon } from "lucide-react";
import { dataService } from "../services/dataService";
import { SectionHeader } from "../components/HelpDialog";
import RefreshButtons from "../components/RefreshButtons";

const SIGNAL_OPTIONS = ["적극매수", "매수", "중립", "매도", "적극매도"];
const RISK_OPTIONS = ["높음", "주의", "낮음"];
const FLOW_OPTIONS = ["순매수", "순매도"];
const MARKET_OPTIONS = ["KOSPI", "KOSDAQ"];

const SECTION_HELP_SCANNER = {
  scanner: {
    title: "종목 스캐너",
    desc: "원하는 조건을 선택하고 검색하면, 조건에 맞는 종목만 필터링됩니다. 여러 필터를 동시에 선택하면 AND 조건으로 모두 충족하는 종목만 표시됩니다.",
  },
};

// Register scanner help
import { SECTION_HELP } from "../components/HelpDialog";
Object.assign(SECTION_HELP, SECTION_HELP_SCANNER);

export default function Scanner({ onToggleTheme, isDark }: { onToggleTheme?: () => void; isDark?: boolean }) {
  const [allStocks, setAllStocks] = useState<any[]>([]);
  const [results, setResults] = useState<any[] | null>(null);
  const [signals, setSignals] = useState<Set<string>>(new Set());
  const [risks, setRisks] = useState<Set<string>>(new Set());
  const [flows, setFlows] = useState<Set<string>>(new Set());
  const [markets, setMarkets] = useState<Set<string>>(new Set());
  const [themeOnly, setThemeOnly] = useState(false);
  const [goldenCross, setGoldenCross] = useState(false);
  const [bnf, setBnf] = useState(false);
  const [shortSelling, setShortSelling] = useState(false);
  const [highBreakout, setHighBreakout] = useState(false);
  const [rsiOverbought, setRsiOverbought] = useState(false);
  const [rsiOversold, setRsiOversold] = useState(false);
  const [dualMatch, setDualMatch] = useState(false);

  useEffect(() => {
    dataService.getScannerStocks().then((data) => {
      if (data) setAllStocks(data);
    });
  }, []);

  function toggle(set: Set<string>, value: string): Set<string> {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  }

  function handleSearch() {
    let filtered = allStocks;
    if (signals.size > 0) filtered = filtered.filter((s) => signals.has(s.signal || ""));
    if (risks.size > 0) filtered = filtered.filter((s) => risks.has(s.risk_level));
    if (flows.size > 0) filtered = filtered.filter((s) => flows.has(s.foreign_flow));
    if (markets.size > 0) filtered = filtered.filter((s) => markets.has(s.market));
    if (themeOnly) filtered = filtered.filter((s) => s.theme);
    if (goldenCross) filtered = filtered.filter((s) => s.golden_cross);
    if (bnf) filtered = filtered.filter((s) => s.bnf);
    if (shortSelling) filtered = filtered.filter((s) => s.short_selling);
    if (highBreakout) filtered = filtered.filter((s) => s.high_breakout);
    if (rsiOverbought) filtered = filtered.filter((s) => s.rsi && s.rsi > 70);
    if (rsiOversold) filtered = filtered.filter((s) => s.rsi && s.rsi < 30);
    if (dualMatch) filtered = filtered.filter((s) => s.match_status === "match");
    filtered.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    setResults(filtered);
  }

  function handleReset() {
    setSignals(new Set());
    setRisks(new Set());
    setFlows(new Set());
    setMarkets(new Set());
    setThemeOnly(false);
    setGoldenCross(false);
    setBnf(false);
    setShortSelling(false);
    setHighBreakout(false);
    setRsiOverbought(false);
    setRsiOversold(false);
    setDualMatch(false);
    setResults(null);
  }

  const activeCount = signals.size + risks.size + flows.size + markets.size + (themeOnly ? 1 : 0)
    + (goldenCross ? 1 : 0) + (bnf ? 1 : 0) + (shortSelling ? 1 : 0) + (highBreakout ? 1 : 0)
    + (rsiOverbought ? 1 : 0) + (rsiOversold ? 1 : 0) + (dualMatch ? 1 : 0);

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      {/* 헤더 — 컴팩트 */}
      <div className="sticky top-0 z-10 -mx-4 px-4 pt-1 pb-0 backdrop-blur-md" style={{ background: 'var(--bg-header)', borderBottom: '1px solid var(--border-light)' }}>
        <div className="flex items-center justify-between">
          <a href="#/" className="text-sm font-bold t-text flex items-center gap-1.5 shrink-0">
            <img src={import.meta.env.BASE_URL + "favicon.svg"} alt="logo" className="w-5 h-5 shrink-0" />
            Stock Toolkit
          </a>
          <div className="flex items-center gap-1 shrink-0">
            <RefreshButtons />
            {onToggleTheme && (
              <button onClick={onToggleTheme} className="p-1 rounded-lg t-text-dim hover:t-text-sub transition" title={isDark ? "라이트 모드" : "다크 모드"}>
                {isDark ? <Sun size={14} /> : <Moon size={14} />}
              </button>
            )}
          </div>
        </div>
        <div className="flex -mx-1 mt-0.5">
          <a href="#/" className="flex-1 text-center py-2 text-xs font-medium t-text-dim hover:t-text-sub transition border-b-2 border-transparent">대시보드</a>
          <a href="#/scanner" className="flex-1 text-center py-2 text-xs font-medium t-accent border-b-2 border-current">종목 스캐너</a>
        </div>
      </div>
      <div className="h-3" />

      <div className="t-card rounded-xl p-4 mb-4 space-y-4">
        <SectionHeader id="scanner">필터 조건</SectionHeader>

        <FilterGroup label="매매 신호" desc="AI가 분석한 종목별 매매 추천 강도">
          {SIGNAL_OPTIONS.map((opt) => (
            <Chip key={opt} label={opt} active={signals.has(opt)} onClick={() => setSignals(toggle(signals, opt))}
              color={opt.includes("매수") ? "red" : opt.includes("매도") ? "blue" : "gray"} />
          ))}
        </FilterGroup>

        <FilterGroup label="위험도" desc="매도 신호 + 외국인 매도 등 위험 요인 개수">
          {RISK_OPTIONS.map((opt) => (
            <Chip key={opt} label={opt} active={risks.has(opt)} onClick={() => setRisks(toggle(risks, opt))}
              color={opt === "높음" ? "red" : opt === "주의" ? "amber" : "green"} />
          ))}
        </FilterGroup>

        <FilterGroup label="외국인 수급" desc="외국인 투자자의 당일 순매수/순매도 방향">
          {FLOW_OPTIONS.map((opt) => (
            <Chip key={opt} label={opt} active={flows.has(opt)} onClick={() => setFlows(toggle(flows, opt))}
              color={opt === "순매수" ? "red" : "blue"} />
          ))}
        </FilterGroup>

        <FilterGroup label="시장" desc="KOSPI(대형주 중심) 또는 KOSDAQ(중소형·기술주)">
          {MARKET_OPTIONS.map((opt) => (
            <Chip key={opt} label={opt} active={markets.has(opt)} onClick={() => setMarkets(toggle(markets, opt))} color="gray" />
          ))}
        </FilterGroup>

        <FilterGroup label="테마" desc="AI가 식별한 당일 주요 테마의 대장주만 표시">
          <Chip label="테마 대장주만" active={themeOnly} onClick={() => setThemeOnly(!themeOnly)} color="purple" />
        </FilterGroup>

        <FilterGroup label="기술적 조건" desc="차트 패턴 및 기술적 지표 기반 필터">
          <Chip label="골든크로스" active={goldenCross} onClick={() => setGoldenCross(!goldenCross)} color="red" />
          <Chip label="52주 신고가" active={highBreakout} onClick={() => setHighBreakout(!highBreakout)} color="red" />
          <Chip label="BNF 적합" active={bnf} onClick={() => setBnf(!bnf)} color="green" />
          <Chip label="공매도 경고" active={shortSelling} onClick={() => setShortSelling(!shortSelling)} color="amber" />
        </FilterGroup>

        <FilterGroup label="RSI" desc="상대강도지수 (70↑ 과매수, 30↓ 과매도)">
          <Chip label="RSI 과매수 (>70)" active={rsiOverbought} onClick={() => setRsiOverbought(!rsiOverbought)} color="red" />
          <Chip label="RSI 과매도 (<30)" active={rsiOversold} onClick={() => setRsiOversold(!rsiOversold)} color="blue" />
        </FilterGroup>

        <FilterGroup label="이중 검증" desc="Vision AI + KIS API 신호 일치 종목">
          <Chip label="이중 매칭" active={dualMatch} onClick={() => setDualMatch(!dualMatch)} color="green" />
        </FilterGroup>
      </div>

      <div className="flex gap-2 mb-5">
        <button onClick={handleSearch}
          className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-xl transition shadow-sm">
          <Search size={18} />
          검색 {activeCount > 0 && `(${activeCount}개 필터)`}
        </button>
        <button onClick={handleReset}
          className="flex items-center gap-1 px-4 bg-gray-100 hover:bg-gray-200 t-text-sub py-3 rounded-xl transition">
          <RotateCcw size={16} />
          초기화
        </button>
      </div>

      {results !== null && (
        <div className="t-card rounded-xl p-4">
          <h2 className="text-base font-semibold t-text mb-3">
            검색 결과 <span className="t-text-dim font-normal text-sm">({results.length}종목)</span>
          </h2>
          {results.length === 0 ? (
            <div className="text-center py-8 t-text-dim">조건에 맞는 종목이 없습니다</div>
          ) : (
            <div className="space-y-1.5">
              {results.map((s, i) => (
                <div key={i} className="flex items-center justify-between p-3 t-card-alt rounded-lg">
                  <div>
                    <span className="text-sm font-medium t-text">{s.name}</span>
                    <span className="text-xs t-text-dim ml-1">{s.code}</span>
                    <div className="text-xs t-text-sub mt-0.5">
                      {s.market}
                      {s.theme && <span className="text-purple-600 ml-1">{s.theme}</span>}
                    </div>
                  </div>
                  <div className="text-right space-y-1">
                    <div className="flex items-center gap-1.5 justify-end">
                      <SignalBadge signal={s.signal} />
                      {s.risk_level !== "낮음" && (
                        <span className={`text-xs px-1.5 py-0.5 rounded-full border ${s.risk_level === "높음" ? "bg-red-50 text-red-600 border-red-200" : "bg-amber-50 text-amber-600 border-amber-200"}`}>
                          {s.risk_level}
                        </span>
                      )}
                    </div>
                    <div className={`text-xs ${s.foreign_flow === "순매수" ? "text-red-500" : "text-blue-500"}`}>
                      외국인 {s.foreign_flow}
                      {s.rsi ? <span className={`ml-1 ${s.rsi > 70 ? "text-red-500" : s.rsi < 30 ? "text-blue-500" : "t-text-dim"}`}>RSI {s.rsi}</span> : null}
                    </div>
                    {s.match_status === "match" && (
                      <div className="text-[10px] text-green-600">이중 매칭 확인</div>
                    )}
                    <div className="flex flex-wrap gap-1 justify-end">
                      {s.golden_cross && <span className="text-[10px] text-red-400">골든크로스</span>}
                      {s.high_breakout && <span className="text-[10px] text-red-400">신고가</span>}
                      {s.foreign_holding_pct != null && <span className="text-[10px] t-text-dim">외보 {s.foreign_holding_pct}%</span>}
                      {s.market_cap_billion != null && <span className="text-[10px] t-text-dim">{s.market_cap_billion}조</span>}
                      {s.total_score != null && <span className="text-[10px] text-purple-500">종합 {s.total_score}점</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {results === null && allStocks.length > 0 && (
        <div className="text-center t-text-dim text-sm py-8">
          전체 {allStocks.length}종목 — 필터를 선택하고 검색하세요
        </div>
      )}
    </div>
  );
}

function FilterGroup({ label, desc, children }: { label: string; desc: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-sm font-medium t-text mb-1">{label}</div>
      <div className="text-xs t-text-dim mb-2">{desc}</div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function Chip({ label, active, onClick, color }: { label: string; active: boolean; onClick: () => void; color: string }) {
  const styles: Record<string, { on: string; off: string }> = {
    red: { on: "bg-red-600 text-white border-red-600", off: "t-card t-text-sub hover:border-red-300" },
    blue: { on: "bg-blue-600 text-white border-blue-600", off: "t-card t-text-sub hover:border-blue-300" },
    amber: { on: "bg-amber-500 text-white border-amber-500", off: "t-card t-text-sub hover:border-amber-300" },
    green: { on: "bg-green-600 text-white border-green-600", off: "t-card t-text-sub hover:border-green-300" },
    purple: { on: "bg-purple-600 text-white border-purple-600", off: "t-card t-text-sub hover:border-purple-300" },
    gray: { on: "bg-gray-700 text-white border-gray-700", off: "t-card t-text-sub hover:border-gray-400" },
  };
  const s = styles[color] || styles.gray;
  return (
    <button onClick={onClick} className={`px-3 py-1.5 rounded-full border text-sm font-medium transition ${active ? s.on : s.off}`}>
      {label}
    </button>
  );
}

function SignalBadge({ signal }: { signal: string }) {
  const cls = signal?.includes("매수") ? "bg-red-50 text-red-700 border-red-200" : signal?.includes("매도") ? "bg-blue-50 text-blue-700 border-blue-200" : "bg-gray-50 t-text-sub border-gray-200";
  return <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${cls}`}>{signal || "—"}</span>;
}
