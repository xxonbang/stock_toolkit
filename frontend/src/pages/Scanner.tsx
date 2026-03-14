import { useEffect, useState } from "react";
import { dataService } from "../services/dataService";

const SIGNAL_OPTIONS = ["적극매수", "매수", "중립", "매도", "적극매도"];
const RISK_OPTIONS = ["높음", "주의", "낮음"];
const FLOW_OPTIONS = ["순매수", "순매도"];
const MARKET_OPTIONS = ["KOSPI", "KOSDAQ"];

export default function Scanner() {
  const [allStocks, setAllStocks] = useState<any[]>([]);
  const [results, setResults] = useState<any[] | null>(null);

  const [signals, setSignals] = useState<Set<string>>(new Set());
  const [risks, setRisks] = useState<Set<string>>(new Set());
  const [flows, setFlows] = useState<Set<string>>(new Set());
  const [markets, setMarkets] = useState<Set<string>>(new Set());
  const [themeOnly, setThemeOnly] = useState(false);

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

    if (signals.size > 0) {
      filtered = filtered.filter((s) => signals.has(s.signal || ""));
    }
    if (risks.size > 0) {
      filtered = filtered.filter((s) => risks.has(s.risk_level));
    }
    if (flows.size > 0) {
      filtered = filtered.filter((s) => flows.has(s.foreign_flow));
    }
    if (markets.size > 0) {
      filtered = filtered.filter((s) => markets.has(s.market));
    }
    if (themeOnly) {
      filtered = filtered.filter((s) => s.theme);
    }

    filtered.sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    setResults(filtered);
  }

  function handleReset() {
    setSignals(new Set());
    setRisks(new Set());
    setFlows(new Set());
    setMarkets(new Set());
    setThemeOnly(false);
    setResults(null);
  }

  const activeCount =
    signals.size + risks.size + flows.size + markets.size + (themeOnly ? 1 : 0);

  return (
    <div className="p-4 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">종목 스캐너</h1>

      {/* 필터 섹션 */}
      <div className="space-y-4 mb-6">
        {/* 매매 신호 */}
        <FilterGroup label="매매 신호">
          {SIGNAL_OPTIONS.map((opt) => (
            <Chip
              key={opt}
              label={opt}
              active={signals.has(opt)}
              onClick={() => setSignals(toggle(signals, opt))}
              color={
                opt.includes("매수")
                  ? "red"
                  : opt.includes("매도")
                    ? "blue"
                    : "gray"
              }
            />
          ))}
        </FilterGroup>

        {/* 위험도 */}
        <FilterGroup label="위험도">
          {RISK_OPTIONS.map((opt) => (
            <Chip
              key={opt}
              label={opt}
              active={risks.has(opt)}
              onClick={() => setRisks(toggle(risks, opt))}
              color={opt === "높음" ? "red" : opt === "주의" ? "yellow" : "green"}
            />
          ))}
        </FilterGroup>

        {/* 외국인 수급 */}
        <FilterGroup label="외국인 수급">
          {FLOW_OPTIONS.map((opt) => (
            <Chip
              key={opt}
              label={opt}
              active={flows.has(opt)}
              onClick={() => setFlows(toggle(flows, opt))}
              color={opt === "순매수" ? "red" : "blue"}
            />
          ))}
        </FilterGroup>

        {/* 시장 */}
        <FilterGroup label="시장">
          {MARKET_OPTIONS.map((opt) => (
            <Chip
              key={opt}
              label={opt}
              active={markets.has(opt)}
              onClick={() => setMarkets(toggle(markets, opt))}
              color="gray"
            />
          ))}
        </FilterGroup>

        {/* 테마 */}
        <FilterGroup label="테마">
          <Chip
            label="테마 대장주만"
            active={themeOnly}
            onClick={() => setThemeOnly(!themeOnly)}
            color="purple"
          />
        </FilterGroup>
      </div>

      {/* 검색/초기화 버튼 */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={handleSearch}
          className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-lg transition"
        >
          검색 {activeCount > 0 && `(${activeCount}개 필터)`}
        </button>
        <button
          onClick={handleReset}
          className="px-4 bg-gray-800 hover:bg-gray-700 text-gray-300 py-3 rounded-lg transition"
        >
          초기화
        </button>
      </div>

      {/* 검색 결과 */}
      {results !== null && (
        <div>
          <h2 className="text-lg font-semibold mb-3">
            검색 결과 ({results.length}종목)
          </h2>
          {results.length === 0 ? (
            <div className="bg-gray-900 rounded-lg p-4 text-gray-500 text-center">
              조건에 맞는 종목이 없습니다
            </div>
          ) : (
            <div className="space-y-2">
              {results.map((s, i) => (
                <div
                  key={i}
                  className="bg-gray-900 rounded-lg p-3"
                >
                  <div className="flex justify-between items-center">
                    <div>
                      <span className="font-medium">{s.name}</span>
                      <span className="text-gray-500 text-sm ml-1">
                        ({s.code})
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-sm font-bold ${
                          s.signal?.includes("매수")
                            ? "text-red-400"
                            : s.signal?.includes("매도")
                              ? "text-blue-400"
                              : "text-gray-400"
                        }`}
                      >
                        {s.signal || "—"}
                      </span>
                      {s.risk_level !== "낮음" && (
                        <span
                          className={`text-xs px-1.5 py-0.5 rounded ${
                            s.risk_level === "높음"
                              ? "bg-red-900 text-red-300"
                              : "bg-yellow-900 text-yellow-300"
                          }`}
                        >
                          {s.risk_level}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex justify-between text-sm text-gray-500 mt-1">
                    <span>
                      {s.market}
                      {s.theme && (
                        <span className="text-purple-400 ml-2">{s.theme}</span>
                      )}
                    </span>
                    <span
                      className={
                        s.foreign_flow === "순매수"
                          ? "text-red-400"
                          : "text-blue-400"
                      }
                    >
                      외국인 {s.foreign_flow}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 전체 종목 수 */}
      {results === null && allStocks.length > 0 && (
        <div className="text-center text-gray-600 text-sm">
          전체 {allStocks.length}종목 — 필터를 선택하고 검색하세요
        </div>
      )}
    </div>
  );
}

function FilterGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-gray-900 rounded-lg p-3">
      <div className="text-sm text-gray-400 mb-2">{label}</div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function Chip({
  label,
  active,
  onClick,
  color,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  color: string;
}) {
  const colors: Record<string, { active: string; inactive: string }> = {
    red: {
      active: "bg-red-600 text-white border-red-500",
      inactive: "bg-gray-800 text-gray-400 border-gray-700",
    },
    blue: {
      active: "bg-blue-600 text-white border-blue-500",
      inactive: "bg-gray-800 text-gray-400 border-gray-700",
    },
    yellow: {
      active: "bg-yellow-600 text-white border-yellow-500",
      inactive: "bg-gray-800 text-gray-400 border-gray-700",
    },
    green: {
      active: "bg-green-600 text-white border-green-500",
      inactive: "bg-gray-800 text-gray-400 border-gray-700",
    },
    purple: {
      active: "bg-purple-600 text-white border-purple-500",
      inactive: "bg-gray-800 text-gray-400 border-gray-700",
    },
    gray: {
      active: "bg-gray-600 text-white border-gray-500",
      inactive: "bg-gray-800 text-gray-400 border-gray-700",
    },
  };

  const c = colors[color] || colors.gray;

  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full border text-sm font-medium transition ${
        active ? c.active : c.inactive
      }`}
    >
      {label}
    </button>
  );
}
