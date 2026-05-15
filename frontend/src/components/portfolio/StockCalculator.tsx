import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Pencil, Plus, RefreshCw, Search, X } from "lucide-react";
import { fetchKisPrices, fetchPaperCalcHistory, savePaperCalcHistory } from "../../lib/supabase";
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

interface ScenarioTab {
  id: string;
  name: string;
  items: SavedItem[];
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

function makeTab(name: string, items: SavedItem[] = []): ScenarioTab {
  return { id: crypto.randomUUID(), name, items };
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export default function StockCalculator({ isOpen, onClose }: Props) {
  const { user } = useAuth();
  const tabsKey = `portfolio_calculator_tabs_${user?.id ?? "anon"}`;
  const legacyKey = `portfolio_calculator_rows_${user?.id ?? "anon"}`;

  // 탭 state 초기화 (마이그레이션 포함)
  const [tabs, setTabs] = useState<ScenarioTab[]>(() => {
    try {
      // 새 키 우선
      const raw = localStorage.getItem(tabsKey);
      if (raw) {
        const parsed = JSON.parse(raw) as { tabs: ScenarioTab[]; activeTabId: string };
        if (Array.isArray(parsed?.tabs) && parsed.tabs.length > 0) return parsed.tabs;
      }
      // 마이그레이션: 기존 키 데이터 → 시나리오 1 items로
      const legacyRaw = localStorage.getItem(legacyKey);
      if (legacyRaw) {
        const legacyItems = JSON.parse(legacyRaw) as SavedItem[];
        if (Array.isArray(legacyItems) && legacyItems.length > 0) {
          return [makeTab("시나리오 1", legacyItems)];
        }
      }
    } catch {
      // ignore
    }
    return [makeTab("시나리오 1")];
  });

  const [activeTabId, setActiveTabId] = useState<string>(() => {
    try {
      const raw = localStorage.getItem(tabsKey);
      if (raw) {
        const parsed = JSON.parse(raw) as { tabs: ScenarioTab[]; activeTabId: string };
        if (parsed?.activeTabId) return parsed.activeTabId;
      }
    } catch {
      // ignore
    }
    return "";
  });

  // activeTabId가 tabs에 없으면 첫 탭으로 보정
  const resolvedActiveTabId = tabs.find((t) => t.id === activeTabId)?.id ?? tabs[0]?.id ?? "";

  // 활성 탭의 items 헬퍼
  const activeItems = tabs.find((t) => t.id === resolvedActiveTabId)?.items ?? [];

  // items를 활성 탭에 업데이트하는 헬퍼
  function setActiveItems(updater: (prev: SavedItem[]) => SavedItem[]) {
    setTabs((prev) =>
      prev.map((t) =>
        t.id === resolvedActiveTabId ? { ...t, items: updater(t.items) } : t
      )
    );
  }

  // 탭 이름 인라인 편집
  const [editingTabId, setEditingTabId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const editInputRef = useRef<HTMLInputElement>(null);

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

  // localStorage 저장 + Supabase 동기화 (paper_calc_history 공유)
  // Supabase는 모달 열기 시 fetch 후에만 save 활성화 (서버 데이터 fetch 전 덮어쓰기 방지)
  const hasFetchedRef = useRef(false);

  // 모달 열릴 때 Supabase fetch (theme-analysis와 공유, 새로고침/재오픈 시마다)
  useEffect(() => {
    if (!isOpen) { hasFetchedRef.current = false; return; }
    if (!user) { hasFetchedRef.current = true; return; }
    let cancelled = false;
    fetchPaperCalcHistory().then((remote) => {
      if (cancelled) return;
      if (remote && remote.tabs.length > 0) {
        setTabs(remote.tabs);
        if (remote.activeTabId) setActiveTabId(remote.activeTabId);
      }
      hasFetchedRef.current = true;
    });
    return () => { cancelled = true; };
  }, [isOpen, user?.id]);

  useEffect(() => {
    // localStorage는 항상 즉시 백업
    try {
      localStorage.setItem(tabsKey, JSON.stringify({ tabs, activeTabId: resolvedActiveTabId }));
      if (localStorage.getItem(legacyKey)) localStorage.removeItem(legacyKey);
    } catch {
      // ignore
    }
    // Supabase는 fetch 후에만 + debounce 500ms
    if (!user || !hasFetchedRef.current) return;
    const timer = setTimeout(() => {
      savePaperCalcHistory({ tabs, activeTabId: resolvedActiveTabId });
    }, 500);
    return () => clearTimeout(timer);
  }, [tabs, resolvedActiveTabId, tabsKey, legacyKey, user?.id]);

  // tabs가 0개로 비면 시나리오 1 자동 생성
  useEffect(() => {
    if (tabs.length === 0) {
      const newTab = makeTab("시나리오 1");
      setTabs([newTab]);
      setActiveTabId(newTab.id);
    }
  }, [tabs.length]);

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

  // 모달 열릴 때 활성 탭 현재가 자동 새로고침
  useEffect(() => {
    if (!isOpen) return;
    const codes = activeItems.map((it) => it.code);
    if (!codes.length) return;
    setRefreshing(true);
    fetchPrices(codes)
      .then((prices) => setLivePrices((prev) => ({ ...prev, ...prices })))
      .finally(() => setRefreshing(false));
    // isOpen 변경 시에만 실행
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // 탭 전환 시 새 탭 items 중 livePrices에 없는 코드 fetch
  useEffect(() => {
    if (!isOpen) return;
    const missing = activeItems
      .map((it) => it.code)
      .filter((c) => livePrices[c] == null);
    if (!missing.length) return;
    fetchPrices(missing).then((prices) =>
      setLivePrices((prev) => ({ ...prev, ...prices }))
    );
    // resolvedActiveTabId 변경 시에만
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvedActiveTabId]);

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

  // 누적 리스트에 추가 (활성 탭)
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
    setActiveItems((prev) => [newItem, ...prev]);
    resetForm();
  }

  function removeItem(id: string) {
    setActiveItems((prev) => prev.filter((it) => it.id !== id));
  }

  function clearAll() {
    if (activeItems.length === 0) return;
    if (!window.confirm(`${activeItems.length}개 항목을 모두 지웁니다. 계속할까요?`)) return;
    setActiveItems(() => []);
  }

  async function refresh() {
    if (refreshing || activeItems.length === 0) return;
    setRefreshing(true);
    try {
      const codes = activeItems.map((it) => it.code);
      const prices = await fetchPrices(codes);
      setLivePrices((prev) => ({ ...prev, ...prices }));
    } finally {
      setRefreshing(false);
    }
  }

  // 종합 계산 (활성 탭)
  const summary = useMemo(() => {
    if (activeItems.length === 0) return null;
    let totalInvest = 0;
    let totalEval = 0;
    let evalAvailable = true;
    for (const it of activeItems) {
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
    return { totalInvest, totalEval, profit, rate, evalAvailable, count: activeItems.length };
  }, [activeItems, livePrices]);

  // 탭 추가
  function addTab() {
    const newTab = makeTab(`시나리오 ${tabs.length + 1}`);
    setTabs((prev) => [...prev, newTab]);
    setActiveTabId(newTab.id);
    resetForm();
  }

  // 탭 삭제
  function removeTab(tabId: string) {
    if (tabs.length <= 1) return;
    const idx = tabs.findIndex((t) => t.id === tabId);
    setTabs((prev) => prev.filter((t) => t.id !== tabId));
    // 삭제된 탭이 활성이면 인접 탭으로 이동
    if (resolvedActiveTabId === tabId) {
      const remaining = tabs.filter((t) => t.id !== tabId);
      const nextIdx = Math.max(0, idx - 1);
      setActiveTabId(remaining[nextIdx]?.id ?? "");
    }
    resetForm();
  }

  // 탭 이름 편집 시작
  function startEditTab(tab: ScenarioTab) {
    setEditingTabId(tab.id);
    setEditingName(tab.name);
    setTimeout(() => editInputRef.current?.focus(), 0);
  }

  // 탭 이름 저장
  function commitTabName() {
    const trimmed = editingName.trim();
    if (trimmed && editingTabId) {
      setTabs((prev) =>
        prev.map((t) => (t.id === editingTabId ? { ...t, name: trimmed } : t))
      );
    }
    setEditingTabId(null);
    setEditingName("");
  }

  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 z-[9999]" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
      <div
        className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[61] w-[calc(100%-2rem)] max-w-lg max-h-[88vh] overflow-y-auto rounded-2xl t-card border t-border-light p-4 anim-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-3">
          <span className="t-text font-semibold text-[14px]">주가 계산기</span>
          <button onClick={onClose} className="p-1 t-text-dim hover:t-text transition" aria-label="닫기">
            <X size={16} />
          </button>
        </div>

        {/* 탭 바 */}
        <div className="flex items-center gap-1 mb-3 overflow-x-auto pb-0.5 [scrollbar-width:thin] [&::-webkit-scrollbar]:h-[3px]">
          {tabs.map((tab) => {
            const isActive = tab.id === resolvedActiveTabId;
            const isEditing = editingTabId === tab.id;
            return (
              <div
                key={tab.id}
                className={`group flex items-center gap-1 px-3 py-1.5 rounded-full shrink-0 cursor-pointer transition text-[12px] ${
                  isActive
                    ? "t-card-alt t-text font-semibold border t-border-light"
                    : "t-text-dim border border-transparent hover:t-text"
                }`}
                onClick={() => {
                  if (!isEditing) {
                    setActiveTabId(tab.id);
                    resetForm();
                  }
                }}
                onDoubleClick={() => startEditTab(tab)}
              >
                {isEditing ? (
                  <input
                    ref={editInputRef}
                    type="text"
                    value={editingName}
                    onChange={(e) => setEditingName(e.target.value)}
                    onBlur={commitTabName}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitTabName();
                      if (e.key === "Escape") { setEditingTabId(null); setEditingName(""); }
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className="bg-transparent outline-none border-b t-border-light text-[12px] w-[90px] t-text"
                    style={{ minWidth: 0 }}
                  />
                ) : (
                  <span>{tab.name}</span>
                )}
                {isActive && !isEditing && (
                  <button
                    onClick={(e) => { e.stopPropagation(); startEditTab(tab); }}
                    className="ml-0.5 opacity-50 hover:opacity-100 transition"
                    aria-label="탭 이름 수정"
                    title="이름 수정"
                  >
                    <Pencil size={10} />
                  </button>
                )}
                {isActive && !isEditing && tabs.length > 1 && (
                  <button
                    onClick={(e) => { e.stopPropagation(); removeTab(tab.id); }}
                    className="ml-0.5 opacity-50 hover:opacity-100 transition"
                    aria-label="탭 삭제"
                  >
                    <X size={11} />
                  </button>
                )}
              </div>
            );
          })}
          {/* 탭 추가 버튼 */}
          <button
            onClick={addTab}
            className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center t-text-dim hover:t-text border t-border-light transition"
            aria-label="새 탭 추가"
          >
            <Plus size={13} />
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
        {activeItems.length > 0 && (
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
              {activeItems.map((it) => {
                const cur = livePrices[it.code];
                const invest = it.assumedPrice * it.quantity;
                const evalAmt = cur != null ? cur * it.quantity : invest;
                const profit = evalAmt - invest;
                const rate = cur != null ? ((cur - it.assumedPrice) / it.assumedPrice) * 100 : 0;
                const hasCur = cur != null;
                return (
                  <li key={it.id} className="flex items-center gap-2 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex items-baseline gap-1.5 min-w-0">
                        <span className="font-semibold text-[13px] truncate t-text">{it.name}</span>
                        <span className="text-[10px] t-text-dim tabular-nums shrink-0">{it.code}</span>
                      </div>
                      <div className="text-[11px] t-text-dim tabular-nums space-y-0.5">
                        <div className="whitespace-nowrap">
                          매수 <span className="font-medium t-text-sub">{fmtNum(it.assumedPrice)}</span>원 × {it.quantity.toLocaleString()}주
                        </div>
                        {hasCur && (
                          <div className="whitespace-nowrap">현재가 {fmtNum(cur)}원</div>
                        )}
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className={`text-[12px] font-bold tabular-nums whitespace-nowrap leading-tight ${hasCur ? (profit >= 0 ? "text-red-500" : "text-blue-500") : "t-text-dim"}`}>
                        {hasCur ? `${profit >= 0 ? "+" : ""}${fmtNum(profit)}원` : "—"}
                      </div>
                      <div className={`text-[10px] font-bold tabular-nums mt-0.5 whitespace-nowrap ${hasCur ? (rate >= 0 ? "text-red-500" : "text-blue-500") : "t-text-dim"}`}>
                        {hasCur ? `${rate >= 0 ? "+" : ""}${rate.toFixed(2)}%` : "—"}
                      </div>
                    </div>
                    <button
                      onClick={() => removeItem(it.id)}
                      className="t-text-dim hover:text-red-400 transition p-1 shrink-0"
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
        {activeItems.length === 0 && !preview && (
          <div className="text-center text-[12px] t-text-dim py-6 rounded-lg border t-border-light">
            종목을 검색하여 가정 매수가와 수량을 입력하면<br />수익률을 시뮬레이션할 수 있습니다
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
