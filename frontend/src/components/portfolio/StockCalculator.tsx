import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, RefreshCw, X } from "lucide-react";
import { fetchKisPrices } from "../../lib/supabase";
import { fetchNaverQuotes, isAfterhoursKR } from "../../lib/naver";

interface StockMasterItem {
  code: string;
  name: string;
  market: string;
}

interface CalcRow {
  id: string; // 고유 key (crypto.randomUUID)
  code: string;
  name: string;
  currentPrice: number | null; // null = 조회 중 or 실패
  priceStatus: "idle" | "loading" | "ok" | "error";
  buyPrice: string;
  quantity: string;
}

const LS_KEY = "portfolio_calculator_rows";

interface Saved {
  code: string;
  name: string;
  buyPrice: string;
  quantity: string;
}

function loadRows(): CalcRow[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return [];
    const saved: Saved[] = JSON.parse(raw);
    return saved.map((s) => ({
      id: crypto.randomUUID(),
      code: s.code,
      name: s.name,
      currentPrice: null,
      priceStatus: "idle" as const,
      buyPrice: s.buyPrice,
      quantity: s.quantity,
    }));
  } catch {
    return [];
  }
}

function saveRows(rows: CalcRow[]) {
  const saved: Saved[] = rows.map((r) => ({
    code: r.code,
    name: r.name,
    buyPrice: r.buyPrice,
    quantity: r.quantity,
  }));
  localStorage.setItem(LS_KEY, JSON.stringify(saved));
}

async function fetchPrices(codes: string[]): Promise<Record<string, number>> {
  if (!codes.length) return {};
  const result: Record<string, number> = {};
  // 시간외 단일가 우선 시도
  if (isAfterhoursKR()) {
    try {
      const naverData = await fetchNaverQuotes(codes);
      for (const code of codes) {
        const q = naverData[code];
        if (q) {
          result[code] = q.overtimePrice ?? q.closePrice;
        }
      }
    } catch {
      // fallthrough to KIS
    }
  }
  // 미수신 코드를 KIS로 보완
  const missing = codes.filter((c) => !result[c]);
  if (missing.length) {
    try {
      const kisData = await fetchKisPrices(missing);
      for (const code of missing) {
        const q = kisData[code];
        if (q) result[code] = q.current_price;
      }
    } catch {
      // ignore
    }
  }
  return result;
}

function fmtNum(n: number): string {
  return n.toLocaleString("ko-KR");
}

export default function StockCalculator() {
  const [open, setOpen] = useState(true);
  const [rows, setRows] = useState<CalcRow[]>(() => loadRows());

  // 검색 관련
  const [searching, setSearching] = useState(false);
  const [searchVal, setSearchVal] = useState("");
  const [suggestions, setSuggestions] = useState<StockMasterItem[]>([]);
  const [stockMaster, setStockMaster] = useState<StockMasterItem[]>([]);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // stock-master lazy fetch
  useEffect(() => {
    if (stockMaster.length) return;
    fetch(import.meta.env.BASE_URL + "data/stock-master.json")
      .then((r) => r.json())
      .then((json) => {
        if (Array.isArray(json?.stocks)) setStockMaster(json.stocks);
      })
      .catch(() => {});
  }, [stockMaster.length]);

  // 검색 input 포커스
  useEffect(() => {
    if (searching) searchInputRef.current?.focus();
  }, [searching]);

  // 자동완성 필터
  useEffect(() => {
    if (!searchVal.trim()) { setSuggestions([]); return; }
    const q = searchVal.trim().toLowerCase();
    const matched = stockMaster
      .filter((s) => s.name.toLowerCase().includes(q) || s.code.includes(q))
      .slice(0, 10);
    setSuggestions(matched);
  }, [searchVal, stockMaster]);

  // rows 변경 시 localStorage 저장
  useEffect(() => {
    saveRows(rows);
  }, [rows]);

  // mount 시 저장된 종목의 현재가 일괄 조회
  useEffect(() => {
    const codes = rows.map((r) => r.code);
    if (!codes.length) return;
    setRows((prev) => prev.map((r) => ({ ...r, priceStatus: "loading" })));
    fetchPrices(codes).then((prices) => {
      setRows((prev) =>
        prev.map((r) => {
          const p = prices[r.code];
          return {
            ...r,
            currentPrice: p ?? null,
            priceStatus: p !== undefined ? "ok" : "error",
          };
        })
      );
    });
    // 의도적으로 의존성 배열 비움 — mount 1회만 실행
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 종목 선택 후 행 추가
  async function addRow(item: StockMasterItem) {
    setSearching(false);
    setSearchVal("");
    setSuggestions([]);

    const newRow: CalcRow = {
      id: crypto.randomUUID(),
      code: item.code,
      name: item.name,
      currentPrice: null,
      priceStatus: "loading",
      buyPrice: "",
      quantity: "",
    };
    setRows((prev) => [...prev, newRow]);

    const prices = await fetchPrices([item.code]);
    const p = prices[item.code];
    setRows((prev) =>
      prev.map((r) =>
        r.id === newRow.id
          ? { ...r, currentPrice: p ?? null, priceStatus: p !== undefined ? "ok" : "error" }
          : r
      )
    );
  }

  function removeRow(id: string) {
    setRows((prev) => prev.filter((r) => r.id !== id));
  }

  function updateRow(id: string, field: "buyPrice" | "quantity", value: string) {
    // 숫자/빈값만 허용
    if (value !== "" && !/^\d+$/.test(value)) return;
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
  }

  function resetAll() {
    setRows([]);
    localStorage.removeItem(LS_KEY);
  }

  async function refreshPrices() {
    const codes = rows.map((r) => r.code);
    if (!codes.length) return;
    setRows((prev) => prev.map((r) => ({ ...r, priceStatus: "loading" })));
    const prices = await fetchPrices(codes);
    setRows((prev) =>
      prev.map((r) => {
        const p = prices[r.code];
        return { ...r, currentPrice: p ?? null, priceStatus: p !== undefined ? "ok" : "error" };
      })
    );
  }

  // 종합 계산
  const summary = (() => {
    let totalBuy = 0;
    let totalEval = 0;
    let valid = false;
    for (const r of rows) {
      const buy = parseInt(r.buyPrice, 10);
      const qty = parseInt(r.quantity, 10);
      const cur = r.currentPrice;
      if (!buy || !qty || cur === null) continue;
      valid = true;
      totalBuy += buy * qty;
      totalEval += cur * qty;
    }
    if (!valid) return null;
    const profit = totalEval - totalBuy;
    const rate = totalBuy > 0 ? (profit / totalBuy) * 100 : 0;
    return { totalBuy, totalEval, profit, rate };
  })();

  return (
    <section className="t-card rounded-xl p-4 mt-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <button
          className="flex items-center gap-1.5 t-text font-semibold text-[14px]"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          주가 계산기
        </button>
        <div className="flex items-center gap-2">
          {rows.length > 0 && (
            <button
              onClick={refreshPrices}
              className="flex items-center gap-1 text-[12px] t-text-dim hover:t-text transition"
              title="현재가 새로고침"
            >
              <RefreshCw size={12} />
              새로고침
            </button>
          )}
          {rows.length > 0 && (
            <button
              onClick={resetAll}
              className="text-[12px] text-red-400 hover:text-red-300 transition"
            >
              전체 초기화
            </button>
          )}
        </div>
      </div>

      {open && (
        <>
          {/* 종목 행 목록 */}
          <div className="space-y-2 mb-3">
            {rows.map((r) => {
              const buy = parseInt(r.buyPrice, 10);
              const qty = parseInt(r.quantity, 10);
              const cur = r.currentPrice;
              const hasBoth = buy > 0 && qty > 0 && cur !== null;
              const profit = hasBoth ? (cur! - buy) * qty : null;
              const rate = hasBoth && buy > 0 ? ((cur! - buy) / buy) * 100 : null;
              const isPos = rate !== null && rate >= 0;

              return (
                <div key={r.id} className="rounded-lg border t-border-light p-2.5 space-y-1.5">
                  {/* 종목명 + 삭제 */}
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-medium t-text">
                      {r.name}{" "}
                      <span className="text-[11px] t-text-dim font-normal">{r.code}</span>
                    </span>
                    <button onClick={() => removeRow(r.id)} className="t-text-dim hover:t-text transition">
                      <X size={14} />
                    </button>
                  </div>

                  {/* 현재가 */}
                  <div className="text-[12px] t-text-dim">
                    현재가:{" "}
                    {r.priceStatus === "loading" ? (
                      <span className="t-text-sub">조회 중...</span>
                    ) : r.currentPrice !== null ? (
                      <span className="t-text font-medium">{fmtNum(r.currentPrice)}원</span>
                    ) : (
                      <span className="text-amber-500">조회 실패</span>
                    )}
                  </div>

                  {/* 입력 */}
                  <div className="grid grid-cols-2 gap-1.5">
                    <div>
                      <label className="text-[11px] t-text-dim block mb-0.5">매수가 (원)</label>
                      <input
                        type="text"
                        inputMode="numeric"
                        value={r.buyPrice}
                        onChange={(e) => updateRow(r.id, "buyPrice", e.target.value)}
                        placeholder="매수가"
                        className="w-full rounded-md px-2 py-1 text-[12px] t-text bg-transparent border t-border-light focus:outline-none focus:border-blue-400 tabular-nums"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] t-text-dim block mb-0.5">수량 (주)</label>
                      <input
                        type="text"
                        inputMode="numeric"
                        value={r.quantity}
                        onChange={(e) => updateRow(r.id, "quantity", e.target.value)}
                        placeholder="수량"
                        className="w-full rounded-md px-2 py-1 text-[12px] t-text bg-transparent border t-border-light focus:outline-none focus:border-blue-400 tabular-nums"
                      />
                    </div>
                  </div>

                  {/* 수익률/손익 */}
                  {hasBoth && rate !== null && profit !== null && (
                    <div className="flex items-center gap-3 text-[12px] pt-0.5 border-t t-border-light">
                      <span className={isPos ? "text-red-500 font-medium" : "text-blue-500 font-medium"}>
                        {isPos ? "+" : ""}{rate.toFixed(2)}%
                      </span>
                      <span className={isPos ? "text-red-500" : "text-blue-500"}>
                        {isPos ? "+" : ""}{fmtNum(profit)}원
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* 종목 추가 버튼 / 검색 input */}
          {searching ? (
            <div className="relative mb-3">
              <input
                ref={searchInputRef}
                type="text"
                value={searchVal}
                onChange={(e) => setSearchVal(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Escape") { setSearching(false); setSearchVal(""); } }}
                placeholder="종목명 또는 코드 검색"
                className="w-full rounded-lg px-3 py-2 text-[13px] t-text border t-border-light bg-transparent focus:outline-none focus:border-blue-400"
              />
              <button
                onClick={() => { setSearching(false); setSearchVal(""); }}
                className="absolute right-2 top-1/2 -translate-y-1/2 t-text-dim hover:t-text"
              >
                <X size={14} />
              </button>
              {/* 자동완성 드롭다운 */}
              {suggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 rounded-lg border t-border-light t-card z-50 shadow-lg overflow-hidden">
                  {suggestions.map((s) => (
                    <button
                      key={s.code}
                      onMouseDown={() => addRow(s)}
                      className="w-full text-left px-3 py-2 text-[13px] t-text hover:bg-blue-500/10 transition flex items-center justify-between"
                    >
                      <span>{s.name}</span>
                      <span className="text-[11px] t-text-dim">{s.code} · {s.market}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => setSearching(true)}
              className="w-full py-2 rounded-lg border t-border-light text-[13px] t-text-sub hover:t-text hover:border-blue-400 transition"
            >
              + 종목 추가
            </button>
          )}

          {/* 종합 요약 */}
          {summary && (
            <div className="mt-3 rounded-lg border t-border-light p-3 space-y-1.5">
              <div className="text-[12px] font-medium t-text mb-2">종합</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                <div className="flex justify-between text-[12px]">
                  <span className="t-text-dim">총 매수금</span>
                  <span className="t-text tabular-nums">{fmtNum(summary.totalBuy)}원</span>
                </div>
                <div className="flex justify-between text-[12px]">
                  <span className="t-text-dim">총 평가금</span>
                  <span className="t-text tabular-nums">{fmtNum(summary.totalEval)}원</span>
                </div>
                <div className="flex justify-between text-[12px] col-span-2 border-t t-border-light pt-1.5 mt-0.5">
                  <span className="t-text-dim font-medium">종합 수익률</span>
                  <span className={`font-bold tabular-nums ${summary.rate >= 0 ? "text-red-500" : "text-blue-500"}`}>
                    {summary.rate >= 0 ? "+" : ""}{summary.rate.toFixed(2)}%
                  </span>
                </div>
                <div className="flex justify-between text-[12px] col-span-2">
                  <span className="t-text-dim">총 손익</span>
                  <span className={`font-medium tabular-nums ${summary.profit >= 0 ? "text-red-500" : "text-blue-500"}`}>
                    {summary.profit >= 0 ? "+" : ""}{fmtNum(summary.profit)}원
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* 빈 상태 */}
          {rows.length === 0 && !searching && (
            <p className="text-center text-[12px] t-text-dim py-2">
              종목을 추가하면 수익률을 계산합니다
            </p>
          )}
        </>
      )}
    </section>
  );
}
