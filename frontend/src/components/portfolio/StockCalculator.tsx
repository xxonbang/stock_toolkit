import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { RefreshCw, Search, X } from "lucide-react";
import { fetchKisPrices } from "../../lib/supabase";
import { fetchNaverQuotes, isAfterhoursKR } from "../../lib/naver";
import { useAuth } from "../../lib/AuthContext";

interface StockMasterItem {
  code: string;
  name: string;
  market: string;
}

/** localStorage에 저장되는 항목 구조 */
interface SavedItem {
  id: string;
  code: string;
  name: string;
  assumedPrice: number;
  quantity: number;
  addedAt: string;
}

function fmtNum(n: number): string {
  return n.toLocaleString("ko-KR");
}

async function fetchPrices(codes: string[]): Promise<Record<string, number>> {
  if (!codes.length) return {};
  const result: Record<string, number> = {};
  if (isAfterhoursKR()) {
    try {
      const naverData = await fetchNaverQuotes(codes);
      for (const code of codes) {
        const q = naverData[code];
        if (q) result[code] = q.overtimePrice ?? q.closePrice;
      }
    } catch {
      // fallthrough to KIS
    }
  }
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

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export default function StockCalculator({ isOpen, onClose }: Props) {
  const { user } = useAuth();
  const storageKey = `portfolio_calculator_rows_${user?.id ?? "anon"}`;

  // 누적 리스트
  const [items, setItems] = useState<SavedItem[]>(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) return [];
      const parsed = JSON.parse(raw) as SavedItem[];
      // id/assumedPrice/quantity 필드 존재 여부로 신규 구조 판별
      if (!Array.isArray(parsed) || parsed.some((it) => typeof it.assumedPrice !== "number")) return [];
      return parsed;
    } catch {
      return [];
    }
  });

  // 현재가 맵 (code → price)
  const [livePrices, setLivePrices] = useState<Record<string, number>>({});
  const [refreshing, setRefreshing] = useState(false);

  // 입력 폼
  const [stockMaster, setStockMaster] = useState<StockMasterItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStock, setSelectedStock] = useState<{ code: string; name: string } | null>(null);
  const [priceSearching, setPriceSearching] = useState(false);
  const [assumedPrice, setAssumedPrice] = useState("");
  const [quantity, setQuantity] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);

  // localStorage 저장
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(items));
    } catch {
      // ignore
    }
  }, [items, storageKey]);

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

  // 모달 열릴 때 누적 리스트 현재가 자동 새로고침
  useEffect(() => {
    if (!isOpen) return;
    const codes = items.map((it) => it.code);
    if (!codes.length) return;
    setRefreshing(true);
    fetchPrices(codes)
      .then((prices) => setLivePrices((prev) => ({ ...prev, ...prices })))
      .finally(() => setRefreshing(false));
    // isOpen 변경 시에만 실행 — items 변경 시 재실행 불필요
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // 자동완성 결과
  const searchResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q || selectedStock) return [];
    return stockMaster
      .filter((s) => s.name.toLowerCase().includes(q) || s.code.includes(q))
      .slice(0, 8);
  }, [searchQuery, selectedStock, stockMaster]);

  // 종목 선택
  async function selectStock(code: string, name: string) {
    setSelectedStock({ code, name });
    setSearchQuery("");
    setPriceSearching(true);
    try {
      const prices = await fetchPrices([code]);
      if (prices[code] !== undefined) {
        setLivePrices((prev) => ({ ...prev, [code]: prices[code] }));
        setAssumedPrice(String(prices[code]));
      }
    } finally {
      setPriceSearching(false);
    }
  }

  // 폼 리셋
  function resetForm() {
    setSelectedStock(null);
    setAssumedPrice("");
    setQuantity("");
    setSearchQuery("");
    setTimeout(() => searchInputRef.current?.focus(), 0);
  }

  // 미리보기 계산
  const preview = useMemo(() => {
    if (!selectedStock) return null;
    const p = parseInt(assumedPrice, 10);
    const q = parseInt(quantity, 10);
    if (!p || !q || p <= 0 || q <= 0) return null;
    const cur = livePrices[selectedStock.code] ?? p;
    const invest = p * q;
    const evalAmt = cur * q;
    const profit = evalAmt - invest;
    const rate = ((cur - p) / p) * 100;
    return { p, q, cur, invest, evalAmt, profit, rate };
  }, [selectedStock, assumedPrice, quantity, livePrices]);

  // 누적 리스트에 추가
  function addItem() {
    if (!selectedStock || !preview) return;
    const newItem: SavedItem = {
      id: crypto.randomUUID(),
      code: selectedStock.code,
      name: selectedStock.name,
      assumedPrice: preview.p,
      quantity: preview.q,
      addedAt: new Date().toISOString(),
    };
    setItems((prev) => [newItem, ...prev]);
    resetForm();
  }

  function removeItem(id: string) {
    setItems((prev) => prev.filter((it) => it.id !== id));
  }

  function clearAll() {
    if (items.length === 0) return;
    if (!window.confirm(`${items.length}개 항목을 모두 지웁니다. 계속할까요?`)) return;
    setItems([]);
    setLivePrices({});
  }

  async function refresh() {
    if (refreshing || items.length === 0) return;
    setRefreshing(true);
    try {
      const codes = items.map((it) => it.code);
      const prices = await fetchPrices(codes);
      setLivePrices((prev) => ({ ...prev, ...prices }));
    } finally {
      setRefreshing(false);
    }
  }

  // 종합 계산
  const summary = useMemo(() => {
    if (items.length === 0) return null;
    let totalInvest = 0;
    let totalEval = 0;
    let evalAvailable = true;
    for (const it of items) {
      const cur = livePrices[it.code];
      const invest = it.assumedPrice * it.quantity;
      totalInvest += invest;
      if (cur != null) {
        totalEval += cur * it.quantity;
      } else {
        evalAvailable = false;
        totalEval += invest;
      }
    }
    const profit = totalEval - totalInvest;
    const rate = totalInvest > 0 ? (profit / totalInvest) * 100 : 0;
    return { totalInvest, totalEval, profit, rate, evalAvailable, count: items.length };
  }, [items, livePrices]);

  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999]" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
      <div
        className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[61] w-[calc(100%-2rem)] max-w-lg max-h-[88vh] overflow-y-auto rounded-2xl t-card border t-border-light p-4 anim-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-4">
          <span className="t-text font-semibold text-[14px]">주가 계산기</span>
          <button onClick={onClose} className="p-1 t-text-dim hover:t-text transition" aria-label="닫기">
            <X size={16} />
          </button>
        </div>

        {/* 1단계: 입력 영역 */}
        <div className="rounded-xl border t-border-light p-3 space-y-3 mb-3">
          <div className="text-[11px] font-semibold t-text-dim uppercase tracking-wider">종목 추가</div>

          {/* 검색 or 선택된 종목 */}
          {!selectedStock ? (
            <div className="relative">
              <div className="flex items-center gap-2">
                <Search size={14} className="t-text-dim shrink-0" />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="종목명 또는 코드 검색"
                  className="w-full rounded-lg px-3 py-2 text-[13px] t-text border t-border-light bg-transparent focus:outline-none focus:border-blue-400"
                />
              </div>
              {searchResults.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 rounded-lg border t-border-light t-card z-50 shadow-lg overflow-hidden">
                  {searchResults.map((s) => (
                    <button
                      key={s.code}
                      onMouseDown={() => selectStock(s.code, s.name)}
                      className="w-full text-left px-3 py-2 text-[13px] t-text hover:bg-blue-500/10 transition flex items-center justify-between"
                    >
                      <span className="font-medium">{s.name}</span>
                      <span className="text-[11px] t-text-dim tabular-nums">{s.code}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-lg px-3 py-2 border t-border-light" style={{ background: "var(--bg)" }}>
              <div>
                <span className="text-[13px] font-medium t-text">{selectedStock.name}</span>
                <span className="ml-2 text-[11px] t-text-dim tabular-nums">{selectedStock.code}</span>
                {priceSearching ? (
                  <span className="ml-2 text-[11px] t-text-sub">현재가 조회 중...</span>
                ) : livePrices[selectedStock.code] != null ? (
                  <span className="ml-2 text-[11px] t-text-dim">
                    현재가 <span className="font-semibold t-text">{fmtNum(livePrices[selectedStock.code])}원</span>
                  </span>
                ) : null}
              </div>
              <button onClick={resetForm} className="t-text-dim hover:t-text transition p-1" aria-label="다른 종목 선택">
                <X size={14} />
              </button>
            </div>
          )}

          {/* 매수가 / 수량 입력 */}
          {selectedStock && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] t-text-dim font-medium block">가정 매수가 (원)</label>
                <input
                  type="text"
                  inputMode="numeric"
                  value={assumedPrice}
                  onChange={(e) => setAssumedPrice(e.target.value.replace(/[^0-9]/g, ""))}
                  placeholder={livePrices[selectedStock.code] != null ? fmtNum(livePrices[selectedStock.code]) : "매수가"}
                  className="w-full rounded-md px-2 py-2 text-[13px] t-text bg-transparent border t-border-light focus:outline-none focus:border-blue-400 tabular-nums"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] t-text-dim font-medium block">수량 (주)</label>
                <input
                  type="text"
                  inputMode="numeric"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value.replace(/[^0-9]/g, ""))}
                  placeholder="수량"
                  className="w-full rounded-md px-2 py-2 text-[13px] t-text bg-transparent border t-border-light focus:outline-none focus:border-blue-400 tabular-nums"
                />
              </div>
            </div>
          )}

          {/* 미리보기 카드 */}
          {preview && (
            <div className="rounded-lg p-3 space-y-2" style={{ background: "var(--bg)" }}>
              <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[12px]">
                <span className="t-text-dim">매수금액</span>
                <span className="text-right font-medium tabular-nums t-text">{fmtNum(preview.invest)}원</span>
                <span className="t-text-dim">평가금액</span>
                <span className="text-right font-medium tabular-nums t-text">{fmtNum(preview.evalAmt)}원</span>
                <span className="t-text-dim">손익</span>
                <span className={`text-right font-semibold tabular-nums ${preview.profit >= 0 ? "text-red-500" : "text-blue-500"}`}>
                  {preview.profit >= 0 ? "+" : ""}{fmtNum(preview.profit)}원
                </span>
              </div>
              <div className="flex items-center justify-between pt-2 border-t t-border-light">
                <span className="text-[12px] t-text-dim">수익률</span>
                <span className={`font-bold tabular-nums text-[13px] ${preview.rate >= 0 ? "text-red-500" : "text-blue-500"}`}>
                  {preview.rate >= 0 ? "+" : ""}{preview.rate.toFixed(2)}%
                </span>
              </div>
            </div>
          )}

          {/* 추가 버튼 */}
          {preview && (
            <button
              onClick={addItem}
              className="w-full py-2.5 rounded-lg text-[13px] font-semibold bg-purple-500 hover:bg-purple-600 text-white transition"
            >
              누적 리스트에 추가
            </button>
          )}
        </div>

        {/* 2단계: 종합 카드 */}
        {summary && (
          <div className="rounded-xl border t-border-light p-4 mb-3">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-semibold t-text-dim uppercase tracking-wider">
                종합 · {summary.count}종목
              </span>
              <button
                onClick={refresh}
                disabled={refreshing}
                className="t-text-dim hover:t-text transition p-1 disabled:opacity-50"
                aria-label="현재가 새로고침"
              >
                <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
              </button>
            </div>
            {/* KPI: 수익률 + 손익 */}
            <div className="flex items-baseline justify-between mb-3 pb-3 border-b t-border-light">
              <div>
                <div className="text-[11px] t-text-dim mb-1">수익률</div>
                <div className={`text-2xl font-bold tabular-nums leading-none ${summary.rate >= 0 ? "text-red-500" : "text-blue-500"}`}>
                  {summary.rate >= 0 ? "+" : ""}{summary.rate.toFixed(2)}<span className="text-base ml-0.5">%</span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-[11px] t-text-dim mb-1">손익</div>
                <div className={`text-[15px] font-semibold tabular-nums ${summary.profit >= 0 ? "text-red-500" : "text-blue-500"}`}>
                  {summary.profit >= 0 ? "+" : ""}{fmtNum(summary.profit)}원
                </div>
              </div>
            </div>
            {/* 매수 / 평가 */}
            <div className="grid grid-cols-2 gap-2 text-[12px]">
              <div className="space-y-0.5">
                <div className="t-text-dim">매수</div>
                <div className="font-medium tabular-nums t-text">{fmtNum(summary.totalInvest)}원</div>
              </div>
              <div className="space-y-0.5 text-right">
                <div className="t-text-dim">평가</div>
                <div className="font-medium tabular-nums t-text">{fmtNum(summary.totalEval)}원</div>
              </div>
            </div>
            {!summary.evalAvailable && (
              <div className="mt-2 text-[11px] t-text-dim flex items-center gap-1.5">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500" />
                일부 종목 현재가 미수집 — 새로고침
              </div>
            )}
          </div>
        )}

        {/* 3단계: 누적 리스트 */}
        {items.length > 0 && (
          <div className="rounded-xl border t-border-light p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-semibold t-text-dim uppercase tracking-wider">누적 리스트</span>
              <button
                onClick={clearAll}
                className="text-[11px] t-text-dim hover:text-red-400 transition"
              >
                전체 지우기
              </button>
            </div>
            <ul className="divide-y" style={{ borderColor: "var(--border)" }}>
              {items.map((it) => {
                const cur = livePrices[it.code];
                const invest = it.assumedPrice * it.quantity;
                const evalAmt = cur != null ? cur * it.quantity : invest;
                const profit = evalAmt - invest;
                const rate = cur != null ? ((cur - it.assumedPrice) / it.assumedPrice) * 100 : 0;
                const hasCur = cur != null;
                return (
                  <li key={it.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex items-baseline gap-2">
                        <span className="font-semibold text-[13px] truncate t-text">{it.name}</span>
                        <span className="text-[10px] t-text-dim tabular-nums shrink-0">{it.code}</span>
                      </div>
                      <div className="text-[11px] t-text-dim tabular-nums">
                        <span className="font-medium t-text-sub">{fmtNum(it.assumedPrice)}</span>원 × {it.quantity.toLocaleString()}주
                        {hasCur && (
                          <span className="ml-2 t-text-dim">현재 {fmtNum(cur)}원</span>
                        )}
                      </div>
                    </div>
                    <div className="text-right shrink-0 space-y-1">
                      <div className={`text-[13px] font-bold tabular-nums leading-tight ${hasCur ? (profit >= 0 ? "text-red-500" : "text-blue-500") : "t-text-dim"}`}>
                        {hasCur ? `${profit >= 0 ? "+" : ""}${fmtNum(profit)}원` : "—"}
                      </div>
                      <div className={`text-[10px] font-bold tabular-nums ${hasCur ? (rate >= 0 ? "text-red-500" : "text-blue-500") : "t-text-dim"}`}>
                        {hasCur ? `${rate >= 0 ? "+" : ""}${rate.toFixed(2)}%` : "—"}
                      </div>
                    </div>
                    <button
                      onClick={() => removeItem(it.id)}
                      className="t-text-dim hover:text-red-400 transition p-1.5 shrink-0"
                      aria-label="삭제"
                    >
                      <X size={14} />
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* 빈 상태 */}
        {items.length === 0 && !preview && (
          <div className="text-center text-[12px] t-text-dim py-6 rounded-lg border t-border-light">
            종목을 검색하여 가정 매수가와 수량을 입력하면<br />수익률을 시뮬레이션할 수 있습니다
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
