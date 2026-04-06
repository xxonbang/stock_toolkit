import { useEffect, useState } from "react";
import { Search, RotateCcw, Sun, Moon, MoreVertical, ChevronDown, X, TrendingUp, TrendingDown, Shield, Zap, Target, AlertTriangle, Sparkles } from "lucide-react";
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
    desc: "프리셋 또는 상세 필터로 종목을 검색합니다. 다중 데이터 소스(signal-pulse, theme-analyzer, KIS API)를 통합하여 종합 투자 점수를 산출합니다.",
  },
};

import { SECTION_HELP } from "../components/HelpDialog";
Object.assign(SECTION_HELP, SECTION_HELP_SCANNER);

type SortKey = "score" | "smart" | "change" | "foreign" | "trading" | "confidence";

const PRESETS: { key: string; label: string; icon: any; desc: string; color: string; apply: (s: any) => boolean }[] = [
  { key: "safe_buy", label: "안전 매수", icon: Shield, desc: "매수 + 낮음 + 순매수 + 이중매칭", color: "text-emerald-400",
    apply: s => (s.signal === "매수" || s.signal === "적극매수") && s.risk_level === "낮음" && s.foreign_flow === "순매수" && s.match_status === "match" },
  { key: "momentum", label: "모멘텀 상승", icon: TrendingUp, desc: "골든크로스 + 신고가 + MA정배열", color: "text-red-400",
    apply: s => s.golden_cross || s.high_breakout || s.ma_aligned },
  { key: "smart_money", label: "스마트머니", icon: Sparkles, desc: "스마트머니 점수 70+ & 매수 신호", color: "text-purple-400",
    apply: s => (s._smart_money_score || 0) >= 70 && (s.signal === "매수" || s.signal === "적극매수") },
  { key: "value", label: "저평가 반등", icon: Target, desc: "PER<15 + 순매수 + 매수 신호", color: "text-blue-400",
    apply: s => s._per > 0 && s._per < 15 && s.foreign_flow === "순매수" && (s.signal === "매수" || s.signal === "적극매수") },
  { key: "danger", label: "위험 경고", icon: AlertTriangle, desc: "매도 + 높음 + 순매도", color: "text-red-500",
    apply: s => (s.signal === "매도" || s.signal === "적극매도") && s.risk_level === "높음" },
  { key: "gapup", label: "갭업 후보", icon: Zap, desc: "갭업 + MA200↑ + 과열X", color: "text-amber-400",
    apply: s => s._gap_pct > 0 && s._gap_pct < 5 && s._above_ma200 },
];

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "score", label: "종합 점수" },
  { key: "smart", label: "스마트머니" },
  { key: "change", label: "등락률" },
  { key: "foreign", label: "외국인 순매수" },
  { key: "trading", label: "거래대금" },
  { key: "confidence", label: "신뢰도" },
];

export default function Scanner({ onToggleTheme, isDark }: { onToggleTheme?: () => void; isDark?: boolean }) {
  const [allStocks, setAllStocks] = useState<any[]>([]);
  const [results, setResults] = useState<any[] | null>(null);
  const [signals, setSignals] = useState<Set<string>>(new Set());
  const [showHeaderMenu, setShowHeaderMenu] = useState(false);
  const [filterCollapsed, setFilterCollapsed] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [risks, setRisks] = useState<Set<string>>(new Set());
  const [flows, setFlows] = useState<Set<string>>(new Set());
  const [markets, setMarkets] = useState<Set<string>>(new Set());
  const [themeOnly, setThemeOnly] = useState(false);
  const [goldenCross, setGoldenCross] = useState(false);
  const [highBreakout, setHighBreakout] = useState(false);
  const [dualMatch, setDualMatch] = useState(false);
  const [maAligned, setMaAligned] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [detail, setDetail] = useState<any | null>(null);

  useEffect(() => {
    // 다중 데이터소스 로드 + JOIN
    Promise.all([
      dataService.getScannerStocks(),
      dataService.getSmartMoney(),
      dataService.getCrossSignal(),
      dataService.getGapAnalysis(),
    ]).then(([scanner, smart, cross, gaps]) => {
      if (!scanner) return;
      const smartMap = new Map((smart || []).map((s: any) => [s.code, s]));
      const crossMap = new Map((cross || []).map((s: any) => [s.code, s]));
      const gapMap = new Map((gaps || []).map((s: any) => [s.code, s]));

      const enriched = scanner.map((s: any) => {
        const sm = smartMap.get(s.code) || {};
        const cs = crossMap.get(s.code) || {};
        const gp = gapMap.get(s.code) || {};
        const apiData = cs.api_data || {};
        const price = apiData.price || {};
        const valuation = apiData.valuation || {};

        // 종합 점수 계산 (100점 만점)
        let investScore = 0;
        // 매매 신호 25점
        const sigScore = s.signal === "적극매수" ? 25 : s.signal === "매수" ? 20 : s.signal === "중립" ? 10 : s.signal === "매도" ? 3 : 0;
        investScore += sigScore;
        // 스마트머니 20점
        investScore += Math.min(20, Math.round((sm.smart_money_score || 0) / 5));
        // 5팩터 스코어 20점
        investScore += Math.min(20, Math.round((s.total_score || 0) / 5));
        // 수급 15점
        if (s.foreign_flow === "순매수") investScore += 10;
        if (s.match_status === "match") investScore += 5;
        // 기술적 10점
        if (s.golden_cross) investScore += 4;
        if (s.high_breakout) investScore += 3;
        if (s.ma_aligned) investScore += 3;
        // 위험 감점
        if (s.risk_level === "높음") investScore -= 15;
        if (s.risk_level === "주의") investScore -= 5;

        return {
          ...s,
          _invest_score: Math.max(0, Math.min(100, investScore)),
          _smart_money_score: sm.smart_money_score || 0,
          _current_price: price.current || 0,
          _change_rate: price.change_rate_pct || 0,
          _per: valuation.per || 0,
          _pbr: valuation.pbr || 0,
          _trading_value: (apiData.ranking || {}).trading_value || 0,
          _foreign_net: s.foreign_net || 0,
          _gap_pct: gp.gap_pct || 0,
          _above_ma200: !!(cs._ma_aligned || cs._golden_cross),
          _consistency: "",
          _signal_age: cs.signal_age_hours || 0,
          _cs: cs,
          _sm: sm,
        };
      });

      setAllStocks(enriched);
    });
  }, []);

  function toggle(set: Set<string>, value: string): Set<string> {
    const next = new Set(set);
    if (next.has(value)) next.delete(value); else next.add(value);
    return next;
  }

  function applyFilters(stocks: any[]): any[] {
    let filtered = stocks;
    if (signals.size > 0) filtered = filtered.filter(s => signals.has(s.signal || ""));
    if (risks.size > 0) filtered = filtered.filter(s => risks.has(s.risk_level));
    if (flows.size > 0) filtered = filtered.filter(s => flows.has(s.foreign_flow));
    if (markets.size > 0) filtered = filtered.filter(s => markets.has(s.market));
    if (themeOnly) filtered = filtered.filter(s => s.theme);
    if (goldenCross) filtered = filtered.filter(s => s.golden_cross);
    if (highBreakout) filtered = filtered.filter(s => s.high_breakout);
    if (maAligned) filtered = filtered.filter(s => s.ma_aligned);
    if (dualMatch) filtered = filtered.filter(s => s.match_status === "match");
    return filtered;
  }

  function sortStocks(stocks: any[]): any[] {
    const sorted = [...stocks];
    switch (sortKey) {
      case "score": sorted.sort((a, b) => b._invest_score - a._invest_score); break;
      case "smart": sorted.sort((a, b) => b._smart_money_score - a._smart_money_score); break;
      case "change": sorted.sort((a, b) => b._change_rate - a._change_rate); break;
      case "foreign": sorted.sort((a, b) => b._foreign_net - a._foreign_net); break;
      case "trading": sorted.sort((a, b) => b._trading_value - a._trading_value); break;
      case "confidence": sorted.sort((a, b) => (b.confidence || 0) - (a.confidence || 0)); break;
    }
    return sorted;
  }

  function handleSearch() {
    setActivePreset(null);
    setResults(sortStocks(applyFilters(allStocks)));
    setFilterCollapsed(true);
  }

  function handlePreset(preset: typeof PRESETS[0]) {
    setActivePreset(preset.key);
    setResults(sortStocks(allStocks.filter(preset.apply)));
    setFilterCollapsed(true);
  }

  function handleReset() {
    setSignals(new Set()); setRisks(new Set()); setFlows(new Set()); setMarkets(new Set());
    setThemeOnly(false); setGoldenCross(false); setHighBreakout(false);
    setMaAligned(false); setDualMatch(false);
    setActivePreset(null); setResults(null); setFilterCollapsed(false);
  }

  const activeCount = signals.size + risks.size + flows.size + markets.size + (themeOnly ? 1 : 0)
    + (goldenCross ? 1 : 0) + (highBreakout ? 1 : 0) + (maAligned ? 1 : 0) + (dualMatch ? 1 : 0);

  return (
    <div className="max-w-2xl mx-auto px-4 pt-0 pb-6">
      {/* 헤더 */}
      <div className="sticky z-10 -mx-4 px-4 pt-2 pb-0 backdrop-blur-md" style={{ top: 'env(safe-area-inset-top, 0px)', background: 'var(--bg-header)', borderBottom: '1px solid var(--border-light)' }}>
        <div className="flex items-center justify-between h-10">
          <a href="#/" className="text-lg font-bold t-text flex items-center gap-2 shrink-0">
            <img src={import.meta.env.BASE_URL + "favicon.svg"} alt="logo" className="w-5 h-5 shrink-0 hover:rotate-12 transition-transform" />
            Stock Toolkit
          </a>
          <div className="flex items-center gap-1 shrink-0">
            {onToggleTheme && (
              <button onClick={onToggleTheme} className="p-1.5 rounded-lg hover:opacity-80 transition" title={isDark ? "라이트 모드" : "다크 모드"}>
                {isDark ? <Sun size={16} className="text-amber-400" /> : <Moon size={16} className="t-text-sub" />}
              </button>
            )}
            <div className="relative">
              <button onClick={() => setShowHeaderMenu(!showHeaderMenu)} className="p-1.5 rounded-lg hover:opacity-80 transition t-text-sub"><MoreVertical size={16} /></button>
              {showHeaderMenu && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setShowHeaderMenu(false)} />
                  <div className="absolute right-0 top-9 z-40 w-48 t-card border t-border-light rounded-xl shadow-lg overflow-hidden">
                    <div className="p-1"><RefreshButtons menuMode /></div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="flex -mx-1 relative">
          {[
            { href: "#/", label: "대시보드" }, { href: "#/portfolio", label: "포트폴리오" },
            { href: "#/scanner", label: "스캐너" }, { href: "#/auto-trader", label: "모의투자" },
          ].map(tab => {
            const active = tab.href === "#/scanner";
            return <a key={tab.href} href={tab.href} className={`flex-1 text-center py-3 text-sm font-medium transition-colors ${active ? "font-semibold t-accent" : "t-text-dim hover:t-text-sub"}`}>{tab.label}</a>;
          })}
          <div className="absolute bottom-0 h-[3px] rounded-full transition-all duration-300 ease-out" style={{ background: 'var(--accent)', width: '25%', left: '50%' }} />
        </div>
      </div>
      <div className="h-3" />

      {/* 프리셋 */}
      <div className="mb-3">
        <div className="text-[11px] font-semibold t-text mb-2">빠른 검색</div>
        <div className="grid grid-cols-3 gap-1.5">
          {PRESETS.map(p => (
            <button key={p.key} onClick={() => handlePreset(p)}
              className={`p-2 rounded-lg text-left transition-all ${activePreset === p.key ? "ring-2 ring-blue-500/50 shadow-sm" : "hover:opacity-80"}`}
              style={{ background: "var(--bg-card)" }}>
              <div className="flex items-center gap-1.5 mb-0.5">
                <p.icon size={12} className={p.color} />
                <span className="text-[10px] font-semibold t-text">{p.label}</span>
              </div>
              <div className="text-[8px] t-text-dim leading-tight">{p.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 상세 필터 */}
      <div className="t-card rounded-xl p-4 mb-4">
        <div className="flex items-center justify-between">
          <button onClick={() => setShowAdvanced(!showAdvanced)} className="flex items-center gap-1.5 text-[11px] font-semibold t-text">
            <ChevronDown size={12} className={`transition-transform ${showAdvanced ? "rotate-0" : "-rotate-90"}`} />
            상세 필터
            {activeCount > 0 && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500 text-white">{activeCount}</span>}
          </button>
          {activeCount > 0 && (
            <button onClick={handleReset} className="text-[10px] t-text-dim hover:t-text transition flex items-center gap-1">
              <RotateCcw size={10} /> 초기화
            </button>
          )}
        </div>
        {showAdvanced && (
          <div className="mt-3 space-y-0.5">
            <FilterGroup label="매매 신호" desc="Vision AI + KIS API 종합">
              {SIGNAL_OPTIONS.map(opt => <Chip key={opt} label={opt} active={signals.has(opt)} onClick={() => setSignals(toggle(signals, opt))} />)}
            </FilterGroup>
            <FilterGroup label="위험도" desc="매도 신호 + 외국인 매도 등">
              {RISK_OPTIONS.map(opt => <Chip key={opt} label={opt} active={risks.has(opt)} onClick={() => setRisks(toggle(risks, opt))} />)}
            </FilterGroup>
            <FilterGroup label="이중 검증" desc="Vision AI + KIS API 일치">
              <Chip label="이중 매칭" active={dualMatch} onClick={() => setDualMatch(!dualMatch)} />
            </FilterGroup>
            <FilterGroup label="기술적 패턴" desc="차트 기반 자동 감지">
              <Chip label="골든크로스" active={goldenCross} onClick={() => setGoldenCross(!goldenCross)} />
              <Chip label="52주 신고가" active={highBreakout} onClick={() => setHighBreakout(!highBreakout)} />
              <Chip label="MA 정배열" active={maAligned} onClick={() => setMaAligned(!maAligned)} />
            </FilterGroup>
            <FilterGroup label="수급·시장" desc="외국인 수급 + 시장">
              {FLOW_OPTIONS.map(opt => <Chip key={opt} label={opt} active={flows.has(opt)} onClick={() => setFlows(toggle(flows, opt))} />)}
              {MARKET_OPTIONS.map(opt => <Chip key={opt} label={opt} active={markets.has(opt)} onClick={() => setMarkets(toggle(markets, opt))} />)}
            </FilterGroup>
            <FilterGroup label="테마" desc="AI 식별 테마 대장주">
              <Chip label="테마 대장주만" active={themeOnly} onClick={() => setThemeOnly(!themeOnly)} />
            </FilterGroup>
            <button onClick={handleSearch}
              className="w-full flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium py-2 rounded-lg transition mt-3">
              <Search size={13} /> 검색{activeCount > 0 ? ` (${activeCount})` : ""}
            </button>
          </div>
        )}
      </div>

      {/* 정렬 + 결과 */}
      {results !== null && (
        <div className="t-card rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold t-text">
              {activePreset ? PRESETS.find(p => p.key === activePreset)?.label : "검색 결과"}
              <span className="t-text-dim font-normal text-xs ml-1">({results.length}종목)</span>
            </h2>
            <select value={sortKey} onChange={e => { const newKey = e.target.value as SortKey; setSortKey(newKey); setResults(prev => { if (!prev) return null; const sorted = [...prev]; switch (newKey) { case "score": sorted.sort((a, b) => b._invest_score - a._invest_score); break; case "smart": sorted.sort((a, b) => b._smart_money_score - a._smart_money_score); break; case "change": sorted.sort((a, b) => b._change_rate - a._change_rate); break; case "foreign": sorted.sort((a, b) => b._foreign_net - a._foreign_net); break; case "trading": sorted.sort((a, b) => b._trading_value - a._trading_value); break; case "confidence": sorted.sort((a, b) => (b.confidence || 0) - (a.confidence || 0)); break; } return sorted; }); }}
              className="text-[10px] t-text-sub rounded-lg px-2 py-1 border t-border-light" style={{ background: "var(--bg)" }}>
              {SORT_OPTIONS.map(o => <option key={o.key} value={o.key}>{o.label}순</option>)}
            </select>
          </div>
          {results.length === 0 ? (
            <div className="text-center py-8 t-text-dim text-sm">조건에 맞는 종목이 없습니다</div>
          ) : (
            <div className="space-y-1.5">
              {results.map((s, i) => (
                <button key={i} onClick={() => setDetail(s)} className="w-full text-left p-3 t-card-alt rounded-lg card-hover transition">
                  <div className="flex items-center justify-between">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-medium t-text">{s.name}</span>
                        <span className="text-[10px] t-text-dim">{s.code}</span>
                        {s.market && <span className="text-[9px] t-text-dim">{s.market}</span>}
                      </div>
                      {s.theme && <div className="text-[9px] text-purple-500 mt-0.5">{s.theme}</div>}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {s._change_rate !== 0 && (
                        <span className={`text-xs font-bold tabular-nums ${s._change_rate >= 0 ? "text-red-400" : "text-blue-400"}`}>
                          {s._change_rate >= 0 ? "+" : ""}{s._change_rate.toFixed(1)}%
                        </span>
                      )}
                      <SignalBadge signal={s.signal} />
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                    <ScoreBadge label="종합" value={s._invest_score} max={100} />
                    {s._smart_money_score > 0 && <ScoreBadge label="스마트" value={s._smart_money_score} max={100} />}
                    {s.total_score > 0 && <ScoreBadge label="5팩터" value={s.total_score} max={100} />}
                    {s.foreign_flow && (
                      <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${s.foreign_flow === "순매수" ? "bg-red-500/10 text-red-400" : "bg-blue-500/10 text-blue-400"}`}>
                        외국인 {s.foreign_flow}
                      </span>
                    )}
                    {s.risk_level !== "낮음" && (
                      <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${s.risk_level === "높음" ? "bg-red-500/10 text-red-400" : "bg-amber-500/10 text-amber-400"}`}>
                        {s.risk_level}
                      </span>
                    )}
                    {s.match_status === "match" && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">이중매칭</span>}
                    {s.golden_cross && <span className="text-[9px] text-red-400">골든크로스</span>}
                    {s.high_breakout && <span className="text-[9px] text-red-400">신고가</span>}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {results === null && allStocks.length > 0 && (
        <div className="text-center t-text-dim text-sm py-8">
          전체 {allStocks.length}종목 — 프리셋 또는 필터로 검색하세요
        </div>
      )}

      {/* 종목 상세 바텀시트 */}
      {detail && (
        <div className="fixed inset-0 z-[9999] anim-fade-in" onClick={() => setDetail(null)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="fixed bottom-0 left-0 right-0 z-[61] max-h-[80vh] flex flex-col rounded-t-2xl t-card border-t t-border-light sm:max-w-lg sm:mx-auto sm:rounded-2xl sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2 anim-slide-up"
            style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 1rem)' }} onClick={e => e.stopPropagation()}>
            <div className="flex-shrink-0 px-5 pt-5">
              <div className="flex items-center justify-center relative mb-3">
                <div className="w-8 h-1 rounded-full sm:hidden" style={{ background: 'var(--border)' }} />
                <button onClick={() => setDetail(null)} className="absolute right-0 top-1/2 -translate-y-1/2 p-1 t-text-dim hover:t-text transition"><X size={18} /></button>
              </div>
              <div className="flex items-center justify-between mb-1">
                <div>
                  <span className="text-base font-bold t-text">{detail.name}</span>
                  <span className="text-xs t-text-dim ml-1.5">{detail.code}</span>
                  {detail.market && <span className="text-xs t-text-dim ml-1">{detail.market}</span>}
                </div>
                <SignalBadge signal={detail.signal} />
              </div>
              {detail.theme && <div className="text-[10px] text-purple-500 mb-2">{detail.theme}</div>}
            </div>
            <div className="flex-1 overflow-y-auto px-5 pb-4 space-y-3">
              {/* 종합 점수 */}
              <DetailSection title="종합 점수">
                <div className="flex items-center gap-3">
                  <div className="text-2xl font-bold t-text">{detail._invest_score}<span className="text-sm t-text-dim">/100</span></div>
                  <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-muted)" }}>
                    <div className={`h-full rounded-full ${detail._invest_score >= 70 ? "bg-red-400" : detail._invest_score >= 40 ? "bg-amber-400" : "bg-blue-400"}`}
                      style={{ width: `${detail._invest_score}%` }} />
                  </div>
                </div>
              </DetailSection>
              {/* 신호 */}
              <DetailSection title="신호">
                <DetailRow label="매매 신호" value={detail.signal || "—"} />
                <DetailRow label="신뢰도" value={detail.confidence ? `${(detail.confidence * 100).toFixed(0)}%` : "—"} />
                <DetailRow label="API 신호" value={detail.api_signal || "—"} />
                <DetailRow label="이중 검증" value={detail.match_status === "match" ? "일치 ✓" : detail.match_status || "—"} color={detail.match_status === "match" ? "text-emerald-400" : undefined} />
                <DetailRow label="위험도" value={detail.risk_level || "—"} color={detail.risk_level === "높음" ? "text-red-400" : detail.risk_level === "주의" ? "text-amber-400" : undefined} />
              </DetailSection>
              {/* 가격 */}
              {detail._current_price > 0 && (
                <DetailSection title="가격">
                  <DetailRow label="현재가" value={`${detail._current_price.toLocaleString()}원`} />
                  <DetailRow label="등락률" value={`${detail._change_rate >= 0 ? "+" : ""}${detail._change_rate.toFixed(2)}%`} color={detail._change_rate >= 0 ? "text-red-400" : "text-blue-400"} />
                  {detail._per > 0 && <DetailRow label="PER" value={detail._per.toFixed(1)} />}
                  {detail._pbr > 0 && <DetailRow label="PBR" value={detail._pbr.toFixed(2)} />}
                </DetailSection>
              )}
              {/* 수급 */}
              <DetailSection title="수급">
                <DetailRow label="외국인" value={detail.foreign_flow || "—"} color={detail.foreign_flow === "순매수" ? "text-red-400" : "text-blue-400"} />
                {detail.foreign_holding_pct > 0 && <DetailRow label="외국인 지분" value={`${detail.foreign_holding_pct}%`} />}
                {detail.market_cap_billion > 0 && <DetailRow label="시가총액" value={detail.market_cap_billion >= 1000000 ? `${(detail.market_cap_billion / 1000000).toFixed(1)}조` : `${Math.round(detail.market_cap_billion / 100).toLocaleString()}억`} />}
              </DetailSection>
              {/* 기술적 */}
              <DetailSection title="기술적 패턴">
                <div className="flex flex-wrap gap-1.5">
                  {detail.golden_cross && <MiniTag label="골든크로스" color="red" />}
                  {detail.high_breakout && <MiniTag label="52주 신고가" color="red" />}
                  {detail.ma_aligned && <MiniTag label="MA 정배열" color="red" />}
                  {detail.momentum && <MiniTag label="모멘텀" color="amber" />}
                  {!detail.golden_cross && !detail.high_breakout && !detail.ma_aligned && !detail.momentum && <span className="text-[10px] t-text-dim">해당 없음</span>}
                </div>
              </DetailSection>
              {/* 스마트머니 */}
              {detail._smart_money_score > 0 && (
                <DetailSection title="스마트머니">
                  <DetailRow label="점수" value={`${detail._smart_money_score}/100`} />
                </DetailSection>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// --- 하위 컴포넌트 ---

function FilterGroup({ label, desc, children }: { label: string; desc: string; children: React.ReactNode }) {
  const colors: Record<string, string> = { "매매 신호": "bg-red-400", "위험도": "bg-amber-400", "이중 검증": "bg-emerald-400", "기술적 패턴": "bg-blue-400", "수급·시장": "bg-cyan-400", "테마": "bg-pink-400" };
  return (
    <div className="py-1.5 border-b t-border-light last:border-b-0">
      <div className="flex items-baseline gap-2 mb-1.5">
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${colors[label] || "bg-gray-400"}`} />
        <span className="text-[12px] font-semibold t-text">{label}</span>
        <span className="text-[9px] t-text-dim">{desc}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all ${active ? "bg-blue-500 text-white shadow-sm" : "t-card-alt t-text-sub hover:bg-blue-500/10 hover:text-blue-400"}`}>
      {label}
    </button>
  );
}

function SignalBadge({ signal }: { signal: string }) {
  const cls = signal?.includes("적극매수") ? "bg-red-500/15 text-red-400 border-red-500/30"
    : signal?.includes("매수") ? "bg-red-500/10 text-red-400 border-red-500/20"
    : signal?.includes("적극매도") ? "bg-blue-500/15 text-blue-400 border-blue-500/30"
    : signal?.includes("매도") ? "bg-blue-500/10 text-blue-400 border-blue-500/20"
    : "bg-gray-500/10 t-text-dim border-gray-500/20";
  return <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${cls}`}>{signal || "—"}</span>;
}

function ScoreBadge({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = Math.round(value / max * 100);
  const color = pct >= 70 ? "text-red-400 bg-red-500/10" : pct >= 40 ? "text-amber-400 bg-amber-500/10" : "text-blue-400 bg-blue-500/10";
  return (
    <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full tabular-nums ${color}`}>
      {label} {value}
    </span>
  );
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg p-3" style={{ background: "var(--bg)" }}>
      <div className="text-[10px] font-semibold t-text-dim mb-2">{title}</div>
      {children}
    </div>
  );
}

function DetailRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between py-0.5">
      <span className="text-[10px] t-text-dim">{label}</span>
      <span className={`text-[11px] font-medium tabular-nums ${color || "t-text"}`}>{value}</span>
    </div>
  );
}

function MiniTag({ label, color }: { label: string; color: "red" | "amber" | "blue" }) {
  const cls = color === "red" ? "bg-red-500/10 text-red-400" : color === "amber" ? "bg-amber-500/10 text-amber-400" : "bg-blue-500/10 text-blue-400";
  return <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full ${cls}`}>{label}</span>;
}
