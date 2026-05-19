import { useEffect, useState, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import { useOutletContext } from "react-router-dom";
import {
  BarChart3, RefreshCw, X, HelpCircle, ChevronDown, ChevronUp, ExternalLink, Calculator, TrendingUp, Clock,
} from "lucide-react";
import { dataService } from "../services/dataService";
import { fetchNaverQuotes, isAfterhoursKR } from "../lib/naver";
import { supabase, fetchKisPrices, fetchPriceConcentration, searchKisStock, fetchHoldingsFromDB, insertHolding, updateHolding, deleteHolding, setAccessToken, STORAGE_KEY, insertTransactions, deleteTransactions, fetchTransactionsForHolding } from "../lib/supabase";
import type { PortfolioHolding, PortfolioTransaction, KisStockPrice, PriceConcentration } from "../lib/supabase";
import StockCalculator from "../components/portfolio/StockCalculator";

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

function signalBadge(signal: string) {
  if (signal?.includes("적극매수")) return <Badge variant="danger">적극매수</Badge>;
  if (signal?.includes("매수")) return <Badge variant="danger">매수</Badge>;
  if (signal?.includes("적극매도")) return <Badge variant="blue">적극매도</Badge>;
  if (signal?.includes("매도")) return <Badge variant="blue">매도</Badge>;
  return <Badge>중립</Badge>;
}

/** 정규장 09:00~15:30(KST, 390분) 중 경과 분.
 *  주말/장 마감 후/평일 장전: 390 (전 영업일 누적 데이터 비교).
 *  → KIS는 휴장일에 마지막 영업일 누적값 반환, 100% 활동 기준으로 비교 의미 있음. */
function marketElapsedMinutes(): number {
  const kst = new Date(Date.now() + 9 * 3600 * 1000);
  const day = kst.getUTCDay();
  // 주말: 전 영업일 데이터 비교 (100% 활동 기준)
  if (day === 0 || day === 6) return 390;
  const minutes = kst.getUTCHours() * 60 + kst.getUTCMinutes();
  const open = 9 * 60, close = 15 * 60 + 30;
  // 평일 장 시작 전: 전일 데이터 비교 (100%)
  if (minutes < open) return 390;
  // 장 마감 후: 100%
  if (minutes >= close) return 390;
  // 정규장: 경과 분
  return minutes - open;
}

/** RVOL 분자 데이터 출처 — UN(KRX+NXT 통합) 즉시 전환 (2026-05-19).
 *  daily_ohlcv가 UN+J fallback으로 매일 갱신되며 NXT 상장 종목 history도 UN으로 통합되어가는 중.
 *  영업일 20일 대기 대신 즉시 UN 사용해 분자/분모 시장 범위 일치(NXT 상장 종목 RVOL 정확화).
 *  NXT 미상장 종목은 volume_un === volume_krx이므로 영향 없음. */
function rvolUseUnVolume(): boolean {
  return true;
}

/** 30일 거래량 순위 계산 — 종목 자신의 지난 30일 거래량 중 오늘 위치 (1위=최고).
 *  반환: { rank, total, percentile, projected } 또는 null.
 *  - 정규장 중에는 시간 보정 적용 (currentVol / elapsed × 390) — RVOL과 일관성
 *    예: 09:30(elapsed=30)에 거래량 1M → 일중 추정치 13M로 history와 비교
 *  - 0 값 필터 + 표본 10 미만이면 null */
function calcVolumeRank30(
  currentVol: number | undefined,
  history: number[] | undefined,
): { rank: number; total: number; percentile: number; projected: number; isProjected: boolean } | null {
  if (!currentVol || currentVol <= 0 || !history || history.length === 0) return null;
  const cleaned = history.filter((v) => v > 0);
  if (cleaned.length < 10) return null;
  // 시간 보정: history는 일 마감 거래량이므로 오늘도 같은 기준으로 환산
  const elapsed = marketElapsedMinutes(); // 1~390
  const projected = elapsed >= 390 ? currentVol : Math.round((currentVol / Math.max(elapsed, 1)) * 390);
  const isProjected = elapsed < 390;
  const all = [...cleaned, projected];
  const sorted = [...all].sort((a, b) => b - a);
  const rank = sorted.findIndex((v) => v === projected) + 1;
  const total = all.length;
  const percentile = (rank / total) * 100;
  return { rank, total, percentile, projected, isProjected };
}

/** VWAP/RVOL 계산. trading_value 또는 avg20d 없으면 해당 값 null. */
function calcVwapRvol(
  kisInfo: KisStockPrice | undefined,
  currentPrice: number,
  avg20d: number | undefined,
): { vwap: number | null; vwapDiffPct: number | null; rvol: number | null } {
  const tv = kisInfo?.trading_value;
  const volUn = kisInfo?.volume;
  const volKrx = kisInfo?.volume_krx;
  const vwap = tv && volUn && volUn > 0 ? tv / volUn : null;
  const vwapDiffPct = vwap && currentPrice > 0 ? ((currentPrice - vwap) / vwap) * 100 : null;

  // RVOL 분자: 마이그레이션 완료 전엔 volume_krx, 완료 후엔 volume(UN)
  const useUn = rvolUseUnVolume();
  const numerator = useUn ? volUn : (volKrx ?? volUn);
  let rvol: number | null = null;
  const elapsed = marketElapsedMinutes();
  if (numerator && avg20d && avg20d > 0) {
    const base = elapsed >= 390 ? avg20d : (avg20d * elapsed) / 390;
    if (base > 0) rvol = numerator / base;
  }
  return { vwap, vwapDiffPct, rvol };
}

interface PortfolioContext {
  supaUser: any;
  onShowLogin: () => void;
  onStockDetail: (detail: any) => void;
  setToastMsg: (msg: string) => void;
  crossSignal: any[] | null;
  smartMoney: any[] | null;
  riskMonitor: any[] | null;
  consecutiveSignals: any;
}

export default function Portfolio() {
  const { supaUser, onShowLogin, onStockDetail, setToastMsg, crossSignal, smartMoney, riskMonitor, consecutiveSignals } = useOutletContext<PortfolioContext>();
  const [portfolio, setPortfolio] = useState<any>(null);
  const [dbHoldings, setDbHoldings] = useState<PortfolioHolding[]>([]);
  const dbHoldingsRef = useRef(dbHoldings);
  dbHoldingsRef.current = dbHoldings;
  const [dbLoading, setDbLoading] = useState(false);
  const [showPortfolioEdit, setShowPortfolioEdit] = useState(false);
  const [showCalculator, setShowCalculator] = useState(false);
  const [editHoldings, setEditHoldings] = useState<any[]>([]);
  const [priceRefreshing, setPriceRefreshing] = useState(false);
  const [livePriceTime, setLivePriceTime] = useState("");
  const [excludedCodes, setExcludedCodes] = useState<Set<string>>(() => {
    try { const s = localStorage.getItem("portfolio_excluded"); return s ? new Set(JSON.parse(s)) : new Set(); } catch { return new Set(); }
  });
  useEffect(() => { localStorage.setItem("portfolio_excluded", JSON.stringify([...excludedCodes])); }, [excludedCodes]);
  const [showHealthHelp, setShowHealthHelp] = useState(false);
  const [showVwapRvolHelp, setShowVwapRvolHelp] = useState(false);
  const [stockSearch, setStockSearch] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [allStockList, setAllStockList] = useState<any[]>([]);
  const [volumeAvg20d, setVolumeAvg20d] = useState<Record<string, number>>({});
  const [volume30dHistory, setVolume30dHistory] = useState<Record<string, number[]>>({});
  const [volume30dSourceDate, setVolume30dSourceDate] = useState<string>("");
  const [showRank30Help, setShowRank30Help] = useState(false);
  const [priceConcentration, setPriceConcentration] = useState<Record<string, PriceConcentration>>({});
  const [showConcentrationHelp, setShowConcentrationHelp] = useState(false);
  const [showStrategyGuide, setShowStrategyGuide] = useState(false);
  const [avgDownTarget, setAvgDownTarget] = useState<any>(null);
  const [avgDownPrice, setAvgDownPrice] = useState("");
  const [avgDownQty, setAvgDownQty] = useState("");
  const [avgDownTab, setAvgDownTab] = useState<"basic" | "target" | "multi">("basic");
  const [targetAvg, setTargetAvg] = useState("");
  const [targetMode, setTargetMode] = useState<"qty" | "price">("qty");  // qty: 가격→수량, price: 수량→가격
  const [targetInput, setTargetInput] = useState("");
  const [multiSteps, setMultiSteps] = useState<{ price: string; qty: string }[]>([{ price: "", qty: "" }]);
  const [showBulkAvgDown, setShowBulkAvgDown] = useState(false);
  const [bulkInputs, setBulkInputs] = useState<Record<string, { price: string; qty: string }>>({});
  const [bulkExcluded, setBulkExcluded] = useState<Set<string>>(new Set());
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [transactionsByHolding, setTransactionsByHolding] = useState<Record<string, PortfolioTransaction[]>>({});
  const kisFullData = useRef<Record<string, KisStockPrice>>({});
  // 시간외 단일가가 적용된 종목 코드 집합
  const [afterhoursCodes, setAfterhoursCodes] = useState<Set<string>>(new Set());

  // 모달 열림 시 body 스크롤 잠금
  const anyModalOpen = !!(showPortfolioEdit || showCalculator || showVwapRvolHelp || showRank30Help || showConcentrationHelp);
  useEffect(() => {
    document.body.style.overflow = anyModalOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [anyModalOpen]);

  // DB 보유종목 기반 포트폴리오 구성 (current_price는 KIS에서 채움)
  const mergedPortfolio = useMemo(() => {
    if (dbHoldings.length === 0) return null;
    const merged = dbHoldings.map((lh) => {
      const avgPrice = lh.avg_price || 0;
      const qty = lh.quantity || 0;
      return {
        code: lh.code, name: lh.name,
        avg_price: avgPrice, quantity: qty,
        current_price: 0, signal: "",
        profit_rate: 0, profit_amount: 0,
        invested: avgPrice * qty, current_value: 0, weight: 0,
      };
    });
    const totalInv = merged.reduce((s, h) => s + h.invested, 0);
    merged.forEach((h) => { h.weight = totalInv ? Math.round(h.invested / totalInv * 100) : 0; });
    return { holdings: merged, summary: {
      total_invested: totalInv, total_value: 0,
      total_profit_rate: 0, total_profit_amount: 0, total_holdings: merged.length,
    }};
  }, [dbHoldings]);

  const autoRefreshed = useRef(false);
  const kisLoaded = useRef(false);
  const kisPrices = useRef<Record<string, number>>({});
  const mergedRef = useRef(mergedPortfolio);
  mergedRef.current = mergedPortfolio;
  // 마운트 즉시 세션 선행 조회 (DB fetch와 병렬)
  const sessionPromise = useRef(supabase.auth.getSession());

  // 물타기 결과를 DB/localStorage에 반영하는 헬퍼
  const applyAvgDown = async (items: { code: string; newAvg: number; newQty: number; addPrice?: number; addQty?: number }[]) => {
    if (supaUser) {
      // 1) transaction insert (추가 매수 정보가 있는 항목만)
      const txRows: { holding_id: string; code: string; name: string; price: number; quantity: number }[] = [];
      for (const item of items) {
        if (!item.addPrice || !item.addQty) continue;
        const existing = dbHoldingsRef.current.find(d => d.code === item.code);
        if (!existing?.id) continue;
        txRows.push({ holding_id: existing.id, code: item.code, name: existing.name, price: item.addPrice, quantity: item.addQty });
      }
      let insertedIds: string[] = [];
      if (txRows.length > 0) {
        const inserted = await insertTransactions(txRows);
        if (!inserted) {
          // insert 실패 시 중단
          throw new Error("매수 이력 저장 실패");
        }
        insertedIds = inserted.map(r => r.id);
      }
      // 2) holdings update
      for (const item of items) {
        const existing = dbHoldingsRef.current.find(d => d.code === item.code);
        if (existing?.id) {
          const ok = await updateHolding(existing.id, { avg_price: item.newAvg, quantity: item.newQty });
          if (!ok && insertedIds.length > 0) {
            // rollback transactions
            await deleteTransactions(insertedIds);
            throw new Error("포트폴리오 갱신 실패 (이력 rollback 완료)");
          }
        }
      }
      // 3) transactions state 갱신
      if (insertedIds.length > 0 && txRows.length > 0) {
        setTransactionsByHolding(prev => {
          const next = { ...prev };
          for (const row of txRows) {
            const existing = dbHoldingsRef.current.find(d => d.code === row.code);
            if (!existing?.id) continue;
            const id = existing.id;
            const newTx: PortfolioTransaction = {
              id: insertedIds[txRows.indexOf(row)] ?? "",
              holding_id: id,
              code: row.code,
              name: row.name,
              price: row.price,
              quantity: row.quantity,
              executed_at: new Date().toISOString(),
            };
            next[id] = [newTx, ...(prev[id] || [])];
          }
          return next;
        });
      }
      const fresh = await fetchHoldingsFromDB();
      setDbHoldings(fresh);
    }
    // localStorage 폴백 (항상)
    try {
      const stored = JSON.parse(localStorage.getItem("portfolio_holdings") || "[]");
      for (const item of items) {
        const idx = stored.findIndex((h: any) => h.code === item.code);
        if (idx >= 0) {
          stored[idx] = { ...stored[idx], avg_price: item.newAvg, quantity: item.newQty };
        }
      }
      localStorage.setItem("portfolio_holdings", JSON.stringify(stored));
    } catch {}
  };

  const applyPrices = (mp: any, pm: Record<string, number>) => {
    const updated = mp.holdings.map((h: any) => {
      const cp = pm[h.code] || h.current_price || 0;
      const ap = h.avg_price || 0;
      const qty = h.quantity || 0;
      return { ...h, current_price: cp, profit_rate: ap && cp ? Math.round((cp - ap) / ap * 10000) / 100 : 0,
        profit_amount: ap && cp ? (cp - ap) * qty : 0, invested: ap * qty, current_value: cp * qty };
    });
    const totalInv = updated.reduce((s: number, x: any) => s + x.invested, 0);
    const totalVal = updated.reduce((s: number, x: any) => s + x.current_value, 0);
    updated.forEach((x: any) => { x.weight = totalInv ? Math.round(x.invested / totalInv * 100) : 0; });
    setPortfolio({ ...mp, holdings: updated, summary: { total_invested: totalInv, total_value: totalVal,
      total_profit_rate: totalInv ? Math.round((totalVal - totalInv) / totalInv * 10000) / 100 : 0,
      total_profit_amount: totalVal - totalInv, total_holdings: updated.length }});
  };

  useEffect(() => {
    if (!mergedPortfolio) return;
    if (autoRefreshed.current) {
      // KIS 완료 전이면 아무것도 안 함 (로딩 유지)
      if (!kisLoaded.current) return;
      // KIS 완료 후 mergedPortfolio 변경(편집 등) → 캐시된 가격 재적용
      applyPrices(mergedPortfolio, kisPrices.current);
      // 신규 추가 종목(kisFullData 없음)이 있으면 추가 fetch — VWAP/RVOL/30일 순위 정상화
      const newCodes = mergedPortfolio.holdings.map((h: any) => h.code).filter((c: string) => c && !kisFullData.current[c]);
      if (newCodes.length > 0) {
        (async () => {
          try {
            const { data: { session } } = await sessionPromise.current;
            if (!session?.access_token) return;
            const kisData = await fetchKisPrices(newCodes);
            kisFullData.current = { ...kisFullData.current, ...kisData };
            const newPriceMap = { ...kisPrices.current };
            for (const [code, p] of Object.entries(kisData)) {
              if (p.current_price) newPriceMap[code] = p.current_price;
            }
            kisPrices.current = newPriceMap;
            const latest = mergedRef.current;
            if (latest) applyPrices(latest, newPriceMap);
          } catch {}
        })();
      }
      return;
    }
    autoRefreshed.current = true;
    const codes = mergedPortfolio.holdings.map((h: any) => h.code).filter(Boolean);
    (async () => {
      let priceMap: Record<string, number> = {};
      try {
        const { data: { session } } = await sessionPromise.current;
        if (session?.access_token && codes.length > 0) {
          const kisData = await fetchKisPrices(codes);
          kisFullData.current = kisData;
          for (const [code, p] of Object.entries(kisData)) {
            if (p.current_price) priceMap[code] = p.current_price;
          }
          const missing = codes.filter((c: string) => !priceMap[c]);
          if (missing.length > 0) {
            const retries = await Promise.allSettled(missing.map((c: string) => searchKisStock(c)));
            retries.forEach((r, i) => {
              if (r.status === "fulfilled" && r.value?.current_price) {
                priceMap[missing[i]] = r.value.current_price;
                kisFullData.current[missing[i]] = r.value;
              }
            });
          }
        }
      } catch {}
      // 네이버 보강: KIS 실패 종목 closePrice fallback + 시간외 OPEN이면 overPrice 우선
      const newAfterhoursCodes = new Set<string>();
      if (codes.length > 0) {
        try {
          const naverMap = await fetchNaverQuotes(codes);
          const afterhoursActive = isAfterhoursKR();
          for (const code of codes) {
            const q = naverMap[code];
            if (!q) continue;
            if (afterhoursActive && q.overtimeStatus === "OPEN" && q.overtimePrice) {
              priceMap[code] = q.overtimePrice;
              newAfterhoursCodes.add(code);
            } else if (!priceMap[code] && q.closePrice) {
              priceMap[code] = q.closePrice;
            }
          }
        } catch (e) {
          console.error("[naver] 마운트 시세 보강 실패:", e);
        }
      }
      setAfterhoursCodes(newAfterhoursCodes);
      kisPrices.current = priceMap;
      kisLoaded.current = true;
      const latest = mergedRef.current;
      if (!latest) return;
      if (Object.keys(priceMap).length > 0) {
        const now = new Date(); const hh = now.getHours();
        setLivePriceTime(`${hh < 12 ? "오전" : "오후"} ${hh === 0 ? 12 : hh > 12 ? hh - 12 : hh}:${now.getMinutes().toString().padStart(2,"0")}`);
      }
      applyPrices(latest, priceMap);
    })();
  }, [mergedPortfolio]);

  // stock-master 로드 (종목 검색용)
  useEffect(() => {
    dataService.getStockMaster().then((m: any) => {
      if (m?.stocks) setAllStockList(m.stocks.map((s: any) => ({ code: s.code, name: s.name, market: s.market || "" })));
    });
  }, []);

  // 20일 평균 거래량 로드 (RVOL 계산용)
  useEffect(() => {
    dataService.getVolumeAvg20d().then((m) => { if (m) setVolumeAvg20d(m); }).catch(() => {});
  }, []);

  // 30일 거래량 히스토리 로드 (30일 순위용)
  useEffect(() => {
    dataService.getVolume30dHistory().then((m: any) => {
      if (!m) return;
      const meta = m._source_last_date;
      if (typeof meta === "string") setVolume30dSourceDate(meta);
      // 메타 키 제외하고 순수 데이터만 추출
      const data: Record<string, number[]> = {};
      for (const [k, v] of Object.entries(m)) {
        if (!k.startsWith("_") && Array.isArray(v)) data[k] = v as number[];
      }
      setVolume30dHistory(data);
    }).catch(() => {});
  }, []);

  // 30일 데이터 stale 일수 계산 (source_last_date 기준)
  const volume30dStaleDays = useMemo(() => {
    if (!volume30dSourceDate || volume30dSourceDate.length !== 8) return null;
    const y = parseInt(volume30dSourceDate.slice(0, 4));
    const m = parseInt(volume30dSourceDate.slice(4, 6)) - 1;
    const d = parseInt(volume30dSourceDate.slice(6, 8));
    if (isNaN(y) || isNaN(m) || isNaN(d)) return null;
    const sourceMs = new Date(y, m, d).getTime();
    const todayMs = new Date().setHours(0, 0, 0, 0);
    return Math.floor((todayMs - sourceMs) / 86400000);
  }, [volume30dSourceDate]);
  const volume30dIsStale = volume30dStaleDays != null && volume30dStaleDays > 7;

  // 가격대별 거래집중도 로드 — 보유 종목 변경 시. localStorage 5분 캐시로 응답 시간 단축.
  useEffect(() => {
    const codes = (portfolio?.holdings || []).map((h: any) => h.code).filter(Boolean);
    if (!codes.length) return;
    const CACHE_KEY = "price_concentration_cache_v1";
    const CACHE_TTL_MS = 5 * 60 * 1000; // 5분
    // 1) localStorage에서 캐시 hit 시도
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (raw) {
        const cached = JSON.parse(raw) as { ts: number; codes: string[]; data: Record<string, PriceConcentration> };
        const fresh = Date.now() - cached.ts < CACHE_TTL_MS;
        const sameCodes = cached.codes.length === codes.length && cached.codes.every((c: string) => codes.includes(c));
        if (fresh && sameCodes && cached.data) {
          setPriceConcentration(cached.data);
          return;
        }
      }
    } catch {
      // fallthrough
    }
    // 2) cache miss → 네트워크 fetch + 캐시 저장
    fetchPriceConcentration(codes).then((m) => {
      if (!m) return;
      setPriceConcentration(m);
      try {
        localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), codes, data: m }));
      } catch {
        // localStorage 용량 초과 등 무시
      }
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [portfolio?.holdings?.length]);

  // 로그인 상태 시 DB에서 보유 종목 로드
  useEffect(() => {
    if (supaUser) {
      setDbLoading(true);
      fetchHoldingsFromDB().then(setDbHoldings).catch(() => {}).finally(() => setDbLoading(false));
    } else {
      setDbHoldings([]);
    }
  }, [supaUser]);

  const refreshPortfolioPrices = async () => {
    if (priceRefreshing) return;
    if (!portfolio?.holdings?.length) {
      setToastMsg("포트폴리오 데이터가 없습니다");
      setTimeout(() => setToastMsg(""), 2500);
      return;
    }
    setPriceRefreshing(true);
    try {
      const codes = portfolio.holdings.map((h: any) => h.code).filter(Boolean);
      let priceMap: Record<string, number> = {};
      let source = "";
      let kisRefreshSuccess = false;
      if (supaUser && codes.length > 0) {
        try {
          // 세션 유효성 먼저 확인 — 무효 시 Edge Function hang 방지
          const { data: { session } } = await supabase.auth.getSession();
          if (session?.access_token) {
            const kisData = await Promise.race([
              fetchKisPrices(codes),
              new Promise<never>((_, reject) => setTimeout(() => reject(new Error("KIS timeout")), 8000)),
            ]);
            // VWAP / RVOL 분자 갱신 — kisFullData에 최신 응답 머지
            kisFullData.current = { ...kisFullData.current, ...kisData };
            for (const [code, p] of Object.entries(kisData)) {
              if (p.current_price) priceMap[code] = p.current_price;
            }
            if (Object.keys(priceMap).length > 0) { source = "KIS"; kisRefreshSuccess = true; }
          }
        } catch (e) {
          console.warn("KIS Edge Function 실패:", e);
        }
      }
      if (!source) {
        try {
          const tvRes = await fetch(import.meta.env.BASE_URL + "data/trading_value.json");
          if (tvRes.ok) for (const s of await tvRes.json() || []) {
            if (s.code && s.current_price && !priceMap[s.code]) priceMap[s.code] = s.current_price;
          }
          if (Object.keys(priceMap).length > 0) source = "캐시";
        } catch {}
      }
      // 네이버 보강: KIS 실패 종목 closePrice fallback + 시간외 OPEN이면 overPrice 우선
      const newAfterhoursCodes = new Set<string>();
      if (codes.length > 0) {
        try {
          const naverMap = await fetchNaverQuotes(codes);
          const afterhoursActive = isAfterhoursKR();
          for (const code of codes) {
            const q = naverMap[code];
            if (!q) continue;
            if (afterhoursActive && q.overtimeStatus === "OPEN" && q.overtimePrice) {
              priceMap[code] = q.overtimePrice;
              newAfterhoursCodes.add(code);
            } else if (!priceMap[code] && q.closePrice) {
              priceMap[code] = q.closePrice;
            }
          }
        } catch (e) {
          console.error("[naver] 시세 보강 실패:", e);
        }
      }
      setAfterhoursCodes(newAfterhoursCodes);
      // 4지표 갱신 — KIS 새로고침 성공 시에만 실행 (rate limit 절약)
      if (kisRefreshSuccess) {
        // avg20d / 30일 history: cron이 갱신한 최신 데이터 재로드
        dataService.getVolumeAvg20d().then((m) => { if (m) setVolumeAvg20d(m); }).catch(() => {});
        dataService.getVolume30dHistory().then((m: any) => {
          if (!m) return;
          const meta = m._source_last_date;
          if (typeof meta === "string") setVolume30dSourceDate(meta);
          const data: Record<string, number[]> = {};
          for (const [k, v] of Object.entries(m)) {
            if (!k.startsWith("_") && Array.isArray(v)) data[k] = v as number[];
          }
          setVolume30dHistory(data);
        }).catch(() => {});
        // 거래집중: 캐시 무효화 후 재fetch
        const CACHE_KEY = "price_concentration_cache_v1";
        localStorage.removeItem(CACHE_KEY);
        fetchPriceConcentration(codes).then((m) => {
          if (!m) return;
          setPriceConcentration(m);
          try {
            localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), codes, data: m }));
          } catch {}
        }).catch(() => {});
      }
      if (Object.keys(priceMap).length > 0) {
        const updated = portfolio.holdings.map((h: any) => {
          const cp = priceMap[h.code] || h.current_price || 0;
          const ap = h.avg_price || 0;
          const qty = h.quantity || 0;
          return { ...h, current_price: cp, profit_rate: ap && cp ? Math.round((cp - ap) / ap * 10000) / 100 : 0,
            profit_amount: ap && cp ? (cp - ap) * qty : 0, invested: ap * qty, current_value: cp * qty };
        });
        const totalInv = updated.reduce((s: number, h: any) => s + h.invested, 0);
        const totalVal = updated.reduce((s: number, h: any) => s + h.current_value, 0);
        updated.forEach((h: any) => { h.weight = totalInv ? Math.round(h.invested / totalInv * 100) : 0; });
        setPortfolio((prev: any) => ({ ...prev, holdings: updated, summary: {
          total_invested: totalInv, total_value: totalVal,
          total_profit_rate: totalInv ? Math.round((totalVal - totalInv) / totalInv * 10000) / 100 : 0,
          total_profit_amount: totalVal - totalInv, total_holdings: updated.length,
        }}));
        const now = new Date();
        const hh = now.getHours();
        setLivePriceTime(`${hh < 12 ? "오전" : "오후"} ${hh === 0 ? 12 : hh > 12 ? hh - 12 : hh}:${now.getMinutes().toString().padStart(2,"0")}`);
      } else {
        setToastMsg("시세 조회 실패 — 장 운영시간에 다시 시도해주세요");
        setTimeout(() => setToastMsg(""), 3000);
      }
    } catch (e) {
      console.error("price refresh failed:", e);
      setToastMsg("시세 새로고침 실패 — 네트워크를 확인해주세요");
      setTimeout(() => setToastMsg(""), 3000);
    }
    finally { setPriceRefreshing(false); }
  };

  if (!supaUser) {
    return (
      <section className="t-card rounded-xl p-6 text-center">
        <BarChart3 size={28} className="mx-auto mb-3 t-text-dim" />
        <div className="text-sm font-semibold t-text mb-1">내 포트폴리오</div>
        <div className="text-[12px] t-text-sub mb-4">로그인하면 보유 종목을 관리하고<br/>실시간 수익률을 확인할 수 있습니다.</div>
        <button onClick={onShowLogin}
          className="text-sm font-medium px-6 py-2 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition">로그인</button>
      </section>
    );
  }

  if (!portfolio) {
    return (
      <section className="t-card rounded-xl p-6 text-center">
        <BarChart3 size={24} className="mx-auto mb-2 t-text-dim" />
        <div className="text-sm t-text-sub">포트폴리오 데이터 로딩 중...</div>
      </section>
    );
  }

  const sm = portfolio.summary || {};
  const profitColor = (r: number) => r > 0 ? "text-red-500" : r < 0 ? "text-blue-500" : "t-text";

  return (<>
    <section className="t-card rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-base font-semibold t-text">내 포트폴리오 <span className="text-sm font-normal t-text-dim">({portfolio.holdings?.length})</span></h2>
        <div className="ml-auto flex items-center gap-2">
          {livePriceTime && (
            <div className="text-center">
              <div className="text-[9px] font-bold text-emerald-400 tracking-wider">LIVE</div>
              <div className="text-[10px] t-text-dim">{livePriceTime}</div>
            </div>
          )}
          <button onClick={refreshPortfolioPrices} disabled={priceRefreshing}
            className="p-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 transition disabled:opacity-50">
            <RefreshCw size={16} className={`text-emerald-500 ${priceRefreshing ? "animate-spin" : ""}`} />
          </button>
          <button onClick={() => {
            const source = dbHoldings.length > 0 ? dbHoldings : (portfolio.holdings || []);
            const sectorMap: Record<string, string> = {};
            for (const hh of portfolio.holdings || []) if (hh.code && hh.sector) sectorMap[hh.code] = hh.sector;
            const merged = JSON.parse(JSON.stringify(source)).map((hh: any) => ({
              ...hh, sector: hh.sector || sectorMap[hh.code] || "",
            }));
            setEditHoldings(merged);
            setShowPortfolioEdit(true);
          }}
            className="text-[11px] px-2.5 py-1.5 rounded-xl border border-blue-500/30 text-blue-400 hover:bg-blue-500/10 transition font-medium">편집</button>
          <button onClick={() => setShowCalculator(true)}
            aria-label="주가 계산기" title="주가 계산기"
            className="p-2 rounded-xl bg-purple-500/10 hover:bg-purple-500/20 transition">
            <Calculator size={16} className="text-purple-500" />
          </button>
        </div>
      </div>
      {/* 총 손익 요약 — 체크된 종목만 계산 */}
      {(() => {
        const included = (portfolio.holdings || []).filter((h: any) => !excludedCodes.has(h.code));
        const filtInv = included.reduce((s: number, h: any) => s + (h.invested || 0), 0);
        const filtVal = included.reduce((s: number, h: any) => s + (h.current_value || 0), 0);
        const filtRate = filtInv ? Math.round((filtVal - filtInv) / filtInv * 10000) / 100 : 0;
        return filtInv > 0 ? (
        <div className="flex items-center justify-between mb-3 p-3 rounded-xl border" style={{
          background: filtRate > 0 ? 'rgba(239,68,68,0.04)' : filtRate < 0 ? 'rgba(59,130,246,0.04)' : 'var(--bg-card-alt)',
          borderColor: filtRate > 0 ? 'rgba(239,68,68,0.12)' : filtRate < 0 ? 'rgba(59,130,246,0.12)' : 'var(--border-light)',
        }}>
          <div>
            <div className="text-[10px] t-text-dim">총 투자금</div>
            <div className="text-sm font-semibold t-text tabular-nums">{filtInv.toLocaleString()}원</div>
          </div>
          <div>
            <div className="text-[10px] t-text-dim">평가금</div>
            <div className="text-sm font-semibold t-text tabular-nums">{filtVal.toLocaleString()}원</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] t-text-dim">총 수익률</div>
            <div className={`text-sm font-bold tabular-nums ${profitColor(filtRate)}`}>
              {filtRate >= 0 ? "+" : ""}{filtRate}%
            </div>
            <div className={`text-[10px] font-medium tabular-nums ${profitColor(filtVal - filtInv)}`}>
              {filtVal - filtInv >= 0 ? "+" : ""}{(filtVal - filtInv).toLocaleString()}원
            </div>
          </div>
        </div>
        ) : null;
      })()}
      {/* 종합 물타기 계산기 — 양전(불타기)/음전(물타기) 모두 대상 */}
      {portfolio.holdings && portfolio.holdings.length > 0 && (
        <button onClick={() => {
          const inputs: Record<string, { price: string; qty: string }> = {};
          for (const h of portfolio.holdings || []) {
            inputs[h.code] = { price: h.current_price?.toString() || "", qty: "" };
          }
          setBulkInputs(inputs);
          setBulkExcluded(new Set());
          setShowBulkAvgDown(true);
        }}
          className="w-full mb-3 py-2 rounded-xl text-[11px] font-medium text-blue-500 border border-blue-500/20 hover:bg-blue-500/5 transition">
          종합 물타기 계산기
        </button>
      )}
      {/* 전체 선택/취소 + 종목별 */}
      {portfolio.holdings?.length > 1 && (
        <div className="flex justify-end mb-1">
          <button className="text-xs t-text-dim px-2 py-1 rounded" onClick={() => {
            const allCodes = portfolio.holdings.map((h: any) => h.code);
            const allExcluded = allCodes.every((c: string) => excludedCodes.has(c));
            setExcludedCodes(allExcluded ? new Set() : new Set(allCodes));
          }}>{portfolio.holdings.every((h: any) => excludedCodes.has(h.code)) ? "전체 선택" : "전체 취소"}</button>
        </div>
      )}
      <div className="space-y-1.5 mb-3">
        {portfolio.holdings?.map((h: any, i: number) => {
          const isExcluded = excludedCodes.has(h.code);
          const detail = [...(crossSignal || []), ...(smartMoney || [])].find((s: any) => s.code === h.code);
          const isExpanded = expandedCode === h.code;
          const kisInfo = kisFullData.current[h.code];
          const { vwap, vwapDiffPct, rvol } = calcVwapRvol(kisInfo, h.current_price, volumeAvg20d[h.code]);
          const useUn = rvolUseUnVolume();
          const todayVol = useUn ? kisInfo?.volume : (kisInfo?.volume_krx ?? kisInfo?.volume);
          const rank30 = calcVolumeRank30(todayVol, volume30dHistory[h.code]);
          const conc = priceConcentration[h.code]?.entries;
          // 52주 위치 계산
          const w52High = kisInfo?.w52_hgpr ?? 0;
          const w52Low = kisInfo?.w52_lwpr ?? 0;
          const w52Position = (w52High > w52Low && h.avg_price > 0)
            ? Math.round((h.avg_price - w52Low) / (w52High - w52Low) * 100)
            : null;
          // 외국인 수급 — smartMoney에서 매칭
          const smData = (smartMoney || []).find((s: any) => s.code === h.code);
          const foreignNet: number | null = smData?.foreign_net ?? null;
          // AI 신호
          const aiSignal: string | null = detail?.signal || h.signal || null;
          return (
          <div key={i} className={`t-card-alt rounded-lg ${isExcluded ? "opacity-40" : ""}`}>
            {/* 헤더 행 */}
            <div className="p-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <input type="checkbox" checked={!isExcluded}
                    onChange={() => setExcludedCodes(prev => {
                      const next = new Set(prev);
                      next.has(h.code) ? next.delete(h.code) : next.add(h.code);
                      return next;
                    })}
                    onClick={(e) => e.stopPropagation()}
                    className="custom-check" />
                  <button className="min-w-0 text-left" onClick={() => detail ? onStockDetail(detail) : onStockDetail({ name: h.name, code: h.code, _noData: true })}>
                    <span className="text-sm font-medium t-text">{h.name}</span>
                    <span className="text-[10px] t-text-dim ml-1">{h.code}</span>
                  </button>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {h.profit_rate != null && h.current_price > 0 && (
                    <div className="flex items-center gap-1.5">
                      <div className="w-10 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-muted)' }}>
                        <div className={`h-full rounded-full ${h.profit_rate >= 0 ? "bg-red-400" : "bg-blue-400"}`}
                          style={{ width: `${Math.min(100, Math.abs(h.profit_rate) * 3)}%` }} />
                      </div>
                      <span className={`text-xs font-bold tabular-nums ${profitColor(h.profit_rate)}`}>
                        {h.profit_rate >= 0 ? "+" : ""}{h.profit_rate}%
                      </span>
                    </div>
                  )}
                  {signalBadge(h.signal)}
                  <button
                    onClick={() => {
                      const next = isExpanded ? null : h.code;
                      setExpandedCode(next);
                      if (next && supaUser) {
                        const holdingId = dbHoldings.find(d => d.code === h.code)?.id;
                        if (holdingId && transactionsByHolding[holdingId] === undefined) {
                          fetchTransactionsForHolding(holdingId).then(txs => {
                            setTransactionsByHolding(prev => ({ ...prev, [holdingId]: txs }));
                          });
                        }
                      }
                    }}
                    className="p-0.5 t-text-dim hover:t-text transition">
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                </div>
              </div>
              {/* 투자 정보 테이블 */}
              <div className="mt-2 rounded-lg text-[10px] tabular-nums overflow-hidden" style={{ background: "var(--bg)" }}>
                <div className="grid grid-cols-[2.5rem_1fr_auto_1fr] gap-x-2 px-3 py-1.5" style={{ borderBottom: "1px solid var(--border-light)" }}>
                  <span className="t-text-dim">매수</span>
                  <span className="t-text text-right">{(h.avg_price || 0).toLocaleString()}</span>
                  <span className="t-text-dim text-center">×{h.quantity}</span>
                  <span className="t-text font-medium text-right">{((h.avg_price || 0) * (h.quantity || 0)).toLocaleString()}원</span>
                </div>
                {h.current_price > 0 && (
                  <div className="grid grid-cols-[2.5rem_1fr_auto_1fr] gap-x-2 px-3 py-1.5">
                    <span className="t-text-dim flex items-center gap-1">
                      현재
                      {afterhoursCodes.has(h.code) && (
                        <span className="text-[9px] font-bold px-1 py-0.5 rounded bg-amber-500/15 text-amber-400 leading-none">시간외</span>
                      )}
                    </span>
                    <span className="t-text text-right">{h.current_price.toLocaleString()}</span>
                    <span className="t-text-dim text-center">×{h.quantity}</span>
                    <span className="t-text font-medium text-right">{(h.current_price * (h.quantity || 0)).toLocaleString()}원</span>
                  </div>
                )}
                {(vwap != null || rvol != null) && (
                  <div className="flex items-center justify-between px-3 py-1" style={{ borderTop: "1px solid var(--border-light)" }}>
                    {vwap != null && (
                      <span className="flex items-center gap-1">
                        <button
                          onClick={(e) => { e.stopPropagation(); setShowVwapRvolHelp(true); }}
                          className="flex items-center gap-0.5 t-text-dim hover:t-text transition"
                          title="VWAP 설명"
                        >
                          VWAP
                          <HelpCircle size={10} />
                        </button>
                        <span className="t-text tabular-nums">{Math.round(vwap).toLocaleString()}원</span>
                        {vwapDiffPct != null && (
                          <span className={`tabular-nums ${vwapDiffPct >= 0 ? "text-red-500" : "text-blue-500"}`}>
                            ({vwapDiffPct >= 0 ? "+" : ""}{vwapDiffPct.toFixed(2)}%)
                          </span>
                        )}
                      </span>
                    )}
                    {rvol != null && (
                      <span className="flex items-center gap-1">
                        <button
                          onClick={(e) => { e.stopPropagation(); setShowVwapRvolHelp(true); }}
                          className="flex items-center gap-0.5 t-text-dim hover:t-text transition"
                          title="RVOL 설명"
                        >
                          RVOL
                          <HelpCircle size={10} />
                        </button>
                        <span className={`tabular-nums ${rvol >= 1.5 ? "text-red-500 font-semibold" : rvol < 0.7 ? "t-text-dim" : "t-text"}`}>
                          {rvol.toFixed(2)}×
                        </span>
                      </span>
                    )}
                  </div>
                )}
                {rank30 != null && (
                  <div className="flex items-center justify-between px-3 py-1" style={{ borderTop: "1px solid var(--border-light)" }}>
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowRank30Help(true); }}
                      className="flex items-center gap-0.5 t-text-dim hover:t-text transition"
                      title="30일 순위 설명"
                    >
                      30일 순위
                      <HelpCircle size={10} />
                      {volume30dIsStale && (
                        <span className="ml-1 text-[9px] font-bold px-1 rounded bg-amber-500/15 text-amber-500 leading-none" title={`데이터 ${volume30dStaleDays}일 stale`}>
                          ⚠ {volume30dStaleDays}일전
                        </span>
                      )}
                    </button>
                    <span className={`tabular-nums ${volume30dIsStale ? "t-text-dim" : rank30.rank <= 3 ? "text-red-500 font-semibold" : rank30.percentile <= 10 ? "text-orange-500" : rank30.percentile <= 50 ? "t-text" : "t-text-dim"}`}>
                      {rank30.isProjected && <span className="t-text-dim mr-1">예상</span>}
                      {rank30.rank}위 / {rank30.total}일 (상위 {rank30.percentile.toFixed(0)}%)
                    </span>
                  </div>
                )}
                {conc && conc.length > 0 && (
                  <div className="flex items-center justify-between px-3 py-1 gap-2" style={{ borderTop: "1px solid var(--border-light)" }}>
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowConcentrationHelp(true); }}
                      className="flex items-center gap-0.5 t-text-dim hover:t-text transition shrink-0"
                      title="거래 집중 설명"
                    >
                      거래 집중
                      <HelpCircle size={10} />
                    </button>
                    <div className="t-text tabular-nums flex flex-wrap justify-end gap-x-1 min-w-0 flex-1">
                      {conc.map((e, idx) => (
                        <span key={e.price} className="whitespace-nowrap">
                          {idx > 0 && <span className="t-text-dim">· </span>}
                          {e.price.toLocaleString()}원
                          <span className={`ml-0.5 ${idx === 0 ? "text-red-500 font-semibold" : "t-text-dim"}`}>({e.pct.toFixed(0)}%)</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              {/* 손익 + 비중 + 물타기 */}
              <div className="flex items-center justify-between mt-1.5 px-0.5">
                <div className="flex items-center gap-2">
                  {h.profit_amount != null && h.current_price > 0 && (
                    <span className={`text-[10px] font-semibold ${profitColor(h.profit_amount)}`}>
                      {h.profit_amount >= 0 ? "+" : ""}{h.profit_amount.toLocaleString()}원
                    </span>
                  )}
                  <span className="text-[9px] t-text-dim">비중 {h.weight}%</span>
                </div>
                {h.current_price > 0 && (
                  <button onClick={(e) => { e.stopPropagation(); setAvgDownTarget(h); setAvgDownPrice(h.current_price?.toString() || ""); setAvgDownQty(""); setAvgDownTab("basic"); setTargetAvg(""); setTargetInput(""); setMultiSteps([{ price: "", qty: "" }]); }}
                    className="text-[9px] px-2.5 py-1 rounded-lg bg-blue-500/10 text-blue-500 font-medium hover:bg-blue-500/20 transition">
                    물타기
                  </button>
                )}
              </div>
            </div>
            {/* 펼친 영역 */}
            {isExpanded && (
              <div className="border-t px-3 py-3 space-y-2.5" style={{ borderColor: "var(--border-light)" }}>
                {/* 52주 대비 매수 위치 */}
                <div>
                  <div className="text-[10px] t-text-dim mb-1">52주 대비 매수 위치</div>
                  {w52Position !== null ? (
                    <>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: "var(--bg-muted)" }}>
                          <div className="h-full rounded-full bg-blue-500/60" style={{ width: `${Math.min(100, Math.max(0, w52Position))}%` }} />
                        </div>
                        <span className="text-[11px] font-bold tabular-nums t-text shrink-0">{w52Position}%</span>
                      </div>
                      <div className="flex justify-between text-[10px] t-text-dim mt-0.5">
                        <span>52저 {w52Low.toLocaleString()}원</span>
                        <span>52고 {w52High.toLocaleString()}원</span>
                      </div>
                    </>
                  ) : (
                    <span className="text-[11px] t-text-dim">데이터 없음 (시세 새로고침 후 확인)</span>
                  )}
                </div>
                {/* 외국인 수급 */}
                <div>
                  <div className="text-[10px] t-text-dim mb-0.5">외국인 수급</div>
                  {foreignNet !== null ? (
                    <span className={`text-[11px] font-medium ${foreignNet >= 0 ? "text-red-500" : "text-blue-500"}`}>
                      외국인 {foreignNet >= 0 ? "+" : ""}{foreignNet.toLocaleString()}주
                    </span>
                  ) : (
                    <span className="text-[11px] t-text-dim">수급 데이터 없음</span>
                  )}
                </div>
                {/* AI 분석 신호 */}
                <div>
                  <div className="text-[10px] t-text-dim mb-0.5">AI 분석 신호</div>
                  {aiSignal && aiSignal !== "분석 대상 외" ? (
                    <span className="text-[11px] t-text">{aiSignal}</span>
                  ) : (
                    <span className="text-[11px] t-text-dim">현재 AI 분석에 미포함</span>
                  )}
                </div>
                {/* 매수 이력 */}
                {supaUser && (() => {
                  const holdingId = dbHoldings.find(d => d.code === h.code)?.id;
                  if (!holdingId) return null;
                  const txs = transactionsByHolding[holdingId];
                  return (
                    <div>
                      <div className="text-[10px] t-text-dim mb-1">매수 이력</div>
                      {txs === undefined ? (
                        <span className="text-[11px] t-text-dim">불러오는 중...</span>
                      ) : txs.length === 0 ? (
                        <span className="text-[11px] t-text-dim">추가 매수 이력 없음</span>
                      ) : (
                        <ul className="space-y-1">
                          {txs.map(tx => (
                            <li key={tx.id} className="flex justify-between items-baseline text-[11px]">
                              <span className="t-text-dim tabular-nums">
                                {new Date(tx.executed_at).toLocaleDateString("ko-KR", { year: "2-digit", month: "2-digit", day: "2-digit" })}
                              </span>
                              <span className="tabular-nums t-text">
                                <span className="font-medium">{tx.price.toLocaleString()}</span>원 ×{" "}
                                <span className="font-medium">{tx.quantity.toLocaleString()}</span>주
                                {tx.note && <span className="t-text-dim ml-1.5 text-[10px]">{tx.note}</span>}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  );
                })()}
                {/* 토스증권 링크 */}
                <a href={`https://www.tossinvest.com/stocks/A${h.code}/order`}
                  target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] text-blue-400 hover:underline">
                  <ExternalLink size={11} />
                  토스증권
                </a>
              </div>
            )}
          </div>
          );
        })}
      </div>
      {/* 리밸런싱 제안 — 시그널+수급+위험 기반 */}
      {(() => {
        const h = portfolio.holdings || [];
        const riskMap: Record<string, any> = {};
        for (const r of riskMonitor || []) if (r.code) riskMap[r.code] = r;
        const streakMap: Record<string, number> = {};
        for (const r of (consecutiveSignals?.and_condition || [])) if (r.code) streakMap[r.code] = r.streak;
        for (const r of (consecutiveSignals?.or_condition || [])) if (r.code && !streakMap[r.code]) streakMap[r.code] = r.streak;

        type Suggestion = { text: string; priority: number; type: "danger" | "warn" | "opportunity" };
        const suggestions: Suggestion[] = [];

        for (const x of h) {
          const sig = x.signal || "";
          const isSell = sig.includes("매도");
          const risk = riskMap[x.code];
          const riskLevel = risk?.level || "";
          const foreignNet = x.foreign_net ?? 0;
          const pr = x.profit_rate ?? 0;
          const streak = streakMap[x.code];
          const items: Suggestion[] = [];

          if (isSell && riskLevel === "높음") items.push({ text: `${x.name} 매도 신호 + 고위험 — 즉시 비중 축소 검토`, priority: 1, type: "danger" });
          else if (isSell) items.push({ text: `${x.name} 매도 신호 감지 — 비중 축소 검토`, priority: 2, type: "warn" });
          if (foreignNet < 0 && (riskLevel === "주의" || riskLevel === "높음")) items.push({ text: `${x.name} 외국인 이탈 + ${riskLevel} — 주의 필요`, priority: 3, type: "warn" });
          if (streak && streak >= 2) items.push({ text: `${x.name} ${streak}일 연속 매집 신호 — 추가 매수 검토`, priority: 4, type: "opportunity" });
          if (pr <= -5) items.push({ text: `${x.name} 손실 ${pr}% — 손절 검토`, priority: 5, type: "warn" });
          else if (pr >= 20) items.push({ text: `${x.name} 수익 +${pr}% — 익절 검토`, priority: 6, type: "opportunity" });

          items.sort((a, b) => a.priority - b.priority);
          suggestions.push(...items.slice(0, 2));
        }
        const sectors = h.map((x: any) => x.sector).filter(Boolean);
        if (sectors.length > 0 && new Set(sectors).size < sectors.length) suggestions.push({ text: "동일 섹터 편중 — 섹터 분산 필요", priority: 7, type: "warn" });

        if (suggestions.length === 0) return null;
        suggestions.sort((a, b) => a.priority - b.priority);
        const typeColor = { danger: "text-red-400", warn: "text-amber-400", opportunity: "text-emerald-400" };
        return (
          <div className="bg-orange-500/8 border border-orange-500/15 rounded-lg p-2.5 mb-3">
            <div className="text-xs font-medium text-orange-400 mb-1">리밸런싱 제안</div>
            {suggestions.map((s, i) => (
              <div key={i} className="text-xs t-text-sub">
                <span className={typeColor[s.type]}>·</span> {s.text}
              </div>
            ))}
          </div>
        );
      })()}
      {/* 건강도 — 다차원 가중 점수 */}
      {(() => {
        const h = portfolio.holdings || [];
        const n = h.length || 1;
        // 1) 수익 건전성 (30점) — 평균 수익률 기반
        const avgPr = h.reduce((s: number, x: any) => s + (x.profit_rate ?? 0), 0) / n;
        const profitScore = Math.max(0, 30 + Math.min(avgPr, 0) * 1.5); // 손실 1%당 -1.5점, 최대 -30
        // 2) 시그널 정합성 (25점) — 매도 신호 종목 비중
        const sellCount = h.filter((x: any) => (x.signal || "").includes("매도")).length;
        const signalScore = Math.max(0, 25 - (sellCount / n) * 50);
        // 3) 수급 방향 (20점) — 외국인 순매도 종목 비중
        const foreignSellCount = h.filter((x: any) => (x.foreign_net ?? 0) < 0).length;
        const supplyScore = Math.max(0, 20 - (foreignSellCount / n) * 40);
        // 4) 분산도 (15점) — HHI + 종목 수
        const sectors = h.map((x: any) => x.sector).filter(Boolean);
        const sectorCounts: Record<string, number> = {};
        sectors.forEach((s: string) => { sectorCounts[s] = (sectorCounts[s] || 0) + 1; });
        const hhi = Object.values(sectorCounts).reduce((s: number, c: number) => s + (c / n) ** 2, 0);
        let diverseScore = 15 * (1 - hhi);
        if (n < 3) diverseScore = Math.max(0, diverseScore - 5);
        diverseScore = Math.max(0, diverseScore);
        // 5) 위험 노출 (10점) — riskMonitor 기반
        const riskMap2: Record<string, string> = {};
        for (const r of riskMonitor || []) if (r.code) riskMap2[r.code] = r.level;
        const highRiskCount = h.filter((x: any) => riskMap2[x.code] === "높음").length;
        const cautionCount = h.filter((x: any) => riskMap2[x.code] === "주의").length;
        const riskScore = Math.max(0, 10 - (highRiskCount / n) * 20 - (cautionCount / n) * 8);
        const total = Math.round(profitScore + signalScore + supplyScore + diverseScore + riskScore);
        const healthColor = total >= 70 ? "text-emerald-500" : total >= 50 ? "text-amber-500" : "text-red-500";
        const healthLabel = total >= 70 ? "양호" : total >= 50 ? "보통" : "개선 필요";
        const axes = [
          { label: "수익", score: Math.round(profitScore), max: 30 },
          { label: "시그널", score: Math.round(signalScore), max: 25 },
          { label: "수급", score: Math.round(supplyScore), max: 20 },
          { label: "분산", score: Math.round(diverseScore), max: 15 },
          { label: "위험", score: Math.round(riskScore), max: 10 },
        ];
        return (<>
      <div className="flex items-center gap-2 text-xs t-text-dim">
        <span>건강도 {total}/100</span>
        <span className={`font-medium ${healthColor}`}>{healthLabel}</span>
        <button onClick={() => setShowHealthHelp(true)} className="t-text-dim hover:t-text-sub"><HelpCircle size={13} /></button>
      </div>
      {/* 건강도 축별 바 */}
      <div className="flex gap-1 mt-1.5">
        {axes.map((a) => (
          <div key={a.label} className="flex-1" title={`${a.label} ${a.score}/${a.max}`}>
            <div className="h-1 rounded-full bg-gray-700 overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${(a.score / a.max) * 100}%`, backgroundColor: (a.score / a.max) >= 0.7 ? "#10b981" : (a.score / a.max) >= 0.4 ? "#f59e0b" : "#ef4444" }} />
            </div>
            <div className="text-[8px] t-text-dim text-center mt-0.5">{a.label}</div>
          </div>
        ))}
      </div>
      {/* 4지표 종합 활용 가이드 — 접기/펼치기 */}
      <div className="mt-3 t-card rounded-lg border t-border-light overflow-hidden">
        <button
          onClick={() => setShowStrategyGuide(v => !v)}
          className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-white/5 transition"
        >
          <span className="text-xs font-semibold t-text flex items-center gap-1.5">
            📊 4지표 종합 활용 가이드 (VWAP · RVOL · 30일 순위 · 거래 집중)
          </span>
          {showStrategyGuide ? <ChevronUp size={14} className="t-text-dim" /> : <ChevronDown size={14} className="t-text-dim" />}
        </button>
        {showStrategyGuide && (
          <div className="px-3 pb-3 pt-1 space-y-3 text-[11px] leading-relaxed t-text-sub border-t t-border-light">

            {/* 1. 각 지표의 본질 */}
            <section>
              <div className="text-[12px] font-semibold t-text mb-1.5">1. 각 지표의 본질</div>
              <ul className="space-y-0.5 pl-1">
                <li><span className="font-semibold t-text">VWAP</span> = 일중 평균 매수자의 본전 가격 → <span className="t-text-dim">방향(강세/약세)</span></li>
                <li><span className="font-semibold t-text">RVOL</span> = 같은 시간대 평소 대비 활력 → <span className="t-text-dim">관심도</span></li>
                <li><span className="font-semibold t-text">30일 순위</span> = 자기 30일 거래량 분포 내 위치 → <span className="t-text-dim">절대 이슈 강도</span></li>
                <li><span className="font-semibold t-text">거래 집중 TOP3</span> = 일중 매물대 → <span className="t-text-dim">지지·저항 가격</span></li>
              </ul>
              <div className="mt-1 t-text-dim italic">핵심: VWAP=방향, RVOL+30일순위=활력×검증, 거래집중=실행가</div>
            </section>

            {/* 2. RVOL × 30일 순위 매트릭스 */}
            <section>
              <div className="text-[12px] font-semibold t-text mb-1.5">2. RVOL × 30일 순위 — 함정 검증 (필수)</div>
              <table className="w-full text-[10.5px] border-collapse">
                <thead>
                  <tr className="t-text-dim border-b t-border-light">
                    <th className="text-left py-1 pr-2">RVOL</th>
                    <th className="text-left py-1 pr-2">30일 순위</th>
                    <th className="text-left py-1 pr-2">해석</th>
                    <th className="text-left py-1">신뢰도</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b t-border-light"><td className="py-1 pr-2">≥1.5×</td><td className="py-1 pr-2">상위 10%</td><td className="py-1 pr-2 text-emerald-400">진짜 폭증</td><td className="py-1">⭐⭐⭐</td></tr>
                  <tr className="border-b t-border-light"><td className="py-1 pr-2">≥1.5×</td><td className="py-1 pr-2">평범</td><td className="py-1 pr-2 text-amber-400">가짜 폭증 (평균이 우연히 낮음)</td><td className="py-1">⚠</td></tr>
                  <tr className="border-b t-border-light"><td className="py-1 pr-2">1.0×</td><td className="py-1 pr-2">상위 5%</td><td className="py-1 pr-2">실제 강한 거래</td><td className="py-1">⭐⭐</td></tr>
                  <tr className="border-b t-border-light"><td className="py-1 pr-2">&lt;0.7×</td><td className="py-1 pr-2">평범</td><td className="py-1 pr-2 t-text-dim">무관심·유동성 부족</td><td className="py-1">—</td></tr>
                  <tr><td className="py-1 pr-2">&lt;0.7×</td><td className="py-1 pr-2">하위 30%</td><td className="py-1 pr-2 text-red-400">침체 (관심 식음)</td><td className="py-1">❌</td></tr>
                </tbody>
              </table>
            </section>

            {/* 3. VWAP × 거래 집중 */}
            <section>
              <div className="text-[12px] font-semibold t-text mb-1.5">3. VWAP × 거래 집중 — 매수가 결정</div>
              <ul className="space-y-0.5 pl-1">
                <li><span className="text-emerald-400">현재가 &gt; VWAP &amp; 현재가 &gt; TOP1</span> → 돌파 후 지지, 추격 매수 가능</li>
                <li><span className="t-text">현재가 &gt; VWAP &amp; 현재가 &lt; TOP1</span> → 저항 미돌파, TOP1 돌파 대기</li>
                <li><span className="text-blue-400">현재가 &lt; VWAP &amp; 현재가 ≈ TOP1</span> → 눌림목 지지, 분할 매수 기회</li>
                <li><span className="text-red-400">현재가 &lt; VWAP &amp; 현재가 ≪ TOP1</span> → 지지선 이탈, falling knife 매수 금지</li>
              </ul>
            </section>

            {/* 4. 시나리오 6선 */}
            <section>
              <div className="text-[12px] font-semibold t-text mb-1.5">4. 종합 시나리오 6선</div>
              <div className="space-y-1.5">
                <div><span className="text-emerald-400 font-semibold">A. Strong Long</span> — VWAP↑ + RVOL≥1.5× + 30일 상위 10% + 현재가&gt;TOP1 → 추격 매수, trailing stop 보호</div>
                <div><span className="text-emerald-400">B. Dip Buy</span> — VWAP −1~−3% + RVOL 1.0~1.3× + 30일 상위 30% + 현재가≈TOP1 → 분할 매수 (RVOL 0.7 미만이면 회피)</div>
                <div><span className="text-amber-400">C. Pump Trap</span> — VWAP↑ + RVOL≥1.5× + 30일 평범 + 현재가≫TOP1 → 가짜 폭증, 회피</div>
                <div><span className="text-red-400">D. Falling Knife</span> — VWAP −3%↓ + RVOL≥1.5× + 30일 상위 5% + 현재가≪TOP1 → 패닉 매도 중, 절대 매수 금지</div>
                <div><span className="t-text-dim">E. Boring Sideway</span> — VWAP ±0.5% + RVOL 0.9~1.1× + 30일 평범 → 관망, catalyst 대기</div>
                <div><span className="text-blue-400">F. Take Profit</span> — 보유 + 현재가≫VWAP(+5%↑) + RVOL 1.5×↑ + 현재가&gt;TOP1 + 30일 상위 3 → 일부 익절 or trailing 타이트</div>
              </div>
            </section>

            {/* 5. 진입/청산 체크리스트 */}
            <section>
              <div className="text-[12px] font-semibold t-text mb-1.5">5. 진입 / 청산 체크리스트</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <div className="font-semibold t-text mb-1">진입 4단계</div>
                  <ol className="list-decimal list-inside space-y-0.5">
                    <li>방향: 현재가 vs VWAP</li>
                    <li>활력: RVOL ≥ 1.0× 만 진입</li>
                    <li>검증: 30일 순위와 RVOL 같은 방향?</li>
                    <li>실행가: 거래집중 TOP1 근처 분할</li>
                  </ol>
                </div>
                <div>
                  <div className="font-semibold t-text mb-1">청산 3단계</div>
                  <ol className="list-decimal list-inside space-y-0.5">
                    <li>약세 전환: VWAP 이탈 + RVOL 1.5×↑</li>
                    <li>이슈 강도: 30일 상위 진입 시 대응</li>
                    <li>매물대 이탈: TOP1 아래 깨지면 손절</li>
                  </ol>
                </div>
              </div>
            </section>

            {/* 6. 핵심 원칙 */}
            <section>
              <div className="text-[12px] font-semibold t-text mb-1.5">6. 핵심 원칙</div>
              <ol className="list-decimal list-inside space-y-0.5">
                <li>단일 지표로 결정 금지</li>
                <li>RVOL ↔ 30일 순위 교차검증 필수 (같은 방향일 때만 신뢰)</li>
                <li>거래집중 TOP1은 지지·저항으로 직접 활용 (일중 한정)</li>
                <li>약세 + 거래 식음 = 매수 금지 (관심 없는 종목은 반등 catalyst 없음)</li>
                <li>VWAP은 일중 한정 — 갭 시초가 발생 시 전일 VWAP 무효</li>
              </ol>
            </section>

            {/* 면책 */}
            <section className="border-t t-border-light pt-2">
              <div className="text-[10.5px] t-text-dim italic">
                ⚠ 4지표는 거래 활력·가격 위치 분석 도구. 펀더멘털·매크로·수급은 미반영. 갭업/갭다운 시초가·시간외에서는 일중 누적 데이터 기반인 VWAP·RVOL 무효. 실거래는 종합 판단 필요.
              </div>
            </section>

          </div>
        )}
      </div>
      {/* 건강도 설명 팝업 */}
      {showHealthHelp && createPortal(
        <div className="fixed inset-0 z-[9999]" onClick={() => setShowHealthHelp(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="fixed bottom-0 left-0 right-0 z-[10000] max-h-[70vh] overflow-y-auto rounded-t-2xl t-card border-t t-border-light p-5 sm:max-w-md sm:mx-auto sm:rounded-2xl sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2 anim-slide-up sm:anim-scale-in"
            onClick={e => e.stopPropagation()}>
            {/* 드래그 핸들 + 닫기 */}
            <div className="flex items-center justify-center relative mb-3">
              <div className="w-8 h-1 rounded-full sm:hidden" style={{ background: 'var(--border)' }} />
              <button onClick={() => setShowHealthHelp(false)} className="absolute right-0 top-1/2 -translate-y-1/2 p-1 t-text-dim hover:t-text transition">
                <X size={16} />
              </button>
            </div>
            <h3 className="text-sm font-bold t-text mb-3">건강도 계산 방법</h3>
            <div className="space-y-2 text-xs t-text-sub">
              <p className="t-text font-medium">5개 축의 합산 점수 (100점 만점)</p>
              {axes.map((a) => (
                <div key={a.label} className="flex items-center gap-2">
                  <span className="font-medium t-text w-12">{a.label}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-gray-700 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${(a.score / a.max) * 100}%`, backgroundColor: (a.score / a.max) >= 0.7 ? "#10b981" : (a.score / a.max) >= 0.4 ? "#f59e0b" : "#ef4444" }} />
                  </div>
                  <span className="w-14 text-right">{a.score}/{a.max}</span>
                </div>
              ))}
              <div className="border-t t-border-light pt-2 mt-2 space-y-1.5 text-[11px]">
                <div><span className="font-medium t-text">수익 (30점)</span> — 보유 종목 평균 수익률 기반. 손실 1%당 1.5점 감점</div>
                <div><span className="font-medium t-text">시그널 (25점)</span> — 매도/적극매도 신호 종목 비중이 높을수록 감점</div>
                <div><span className="font-medium t-text">수급 (20점)</span> — 외국인 순매도 종목 비중이 높을수록 감점</div>
                <div><span className="font-medium t-text">분산 (15점)</span> — 섹터 집중도(HHI) + 종목 수 3개 미만 시 추가 감점</div>
                <div><span className="font-medium t-text">위험 (10점)</span> — 고위험/주의 등급 종목 비중이 높을수록 감점</div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
      </>);
      })()}
    </section>
    <StockCalculator isOpen={showCalculator} onClose={() => setShowCalculator(false)} />
    {/* VWAP / RVOL 설명 팝업 */}
    {showVwapRvolHelp && createPortal(
      <div className="fixed inset-0 z-[9999]" onClick={() => setShowVwapRvolHelp(false)}>
        <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
        <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[10000] w-[calc(100%-2rem)] max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl t-card border t-border-light p-5 anim-scale-in"
          onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-3">
            <span className="t-text font-semibold text-[15px]">VWAP / RVOL 안내</span>
            <button onClick={() => setShowVwapRvolHelp(false)} className="p-1 t-text-dim hover:t-text transition" aria-label="닫기">
              <X size={16} />
            </button>
          </div>

          {/* VWAP */}
          <div className="mb-4">
            <div className="text-[13px] font-semibold t-text mb-1 flex items-center gap-1.5">
              <BarChart3 size={14} className="text-emerald-500" />
              VWAP — 거래량 가중 평균가
            </div>
            <div className="text-[12px] t-text-sub leading-relaxed">
              오늘 시장 참가자들의 평균 매수가. <br />
              <span className="font-mono text-[11px] t-text-dim">VWAP = 누적 거래대금 ÷ 누적 거래량</span>
            </div>
            <ul className="mt-2 space-y-1 text-[11px] t-text-sub">
              <li><span className="text-red-500 font-semibold">현재가 &gt; VWAP</span> → 평균 매수자보다 비싸게 사야 함 (강세)</li>
              <li><span className="text-blue-500 font-semibold">현재가 &lt; VWAP</span> → 평균 매수자보다 싸게 살 수 있음 (약세 or 기회)</li>
            </ul>
          </div>

          {/* RVOL */}
          <div className="mb-4">
            <div className="text-[13px] font-semibold t-text mb-1 flex items-center gap-1.5">
              <TrendingUp size={14} className="text-red-500" />
              RVOL — 상대 거래량
            </div>
            <div className="text-[12px] t-text-sub leading-relaxed">
              지금까지의 거래량이 평소 대비 몇 배인지. <br />
              <span className="font-mono text-[11px] t-text-dim">RVOL = 현재 누적 거래량 ÷ (20일 평균 × 경과시간/390분)</span>
            </div>
            <ul className="mt-2 space-y-1 text-[11px] t-text-sub">
              <li><span className="t-text-dim">~ 1.0×</span> 평소 수준 (정상 활동)</li>
              <li><span className="t-text font-semibold">1.0× ~ 1.5×</span> 약간 활발</li>
              <li><span className="text-red-500 font-semibold">≥ 1.5×</span> 평소보다 50%+ 활발 → 시장 관심 증가</li>
              <li><span className="t-text-dim">&lt; 0.7×</span> 평소보다 조용함</li>
            </ul>
          </div>

          {/* 마이그레이션 일정 */}
          <div className="rounded-lg border t-border-light p-3 mb-1" style={{ background: "var(--bg)" }}>
            <div className="text-[11px] font-semibold t-text mb-1.5 flex items-center gap-1.5">
              <Clock size={12} className="t-text-sub" />
              마이그레이션 일정 (NXT 통합)
            </div>
            <div className="text-[10px] t-text-sub leading-relaxed">
              KIS NXT(애프터마켓) 시장 통합으로 거래량 데이터 정합화 중:
            </div>
            <div className="mt-2 space-y-1.5 text-[10px]">
              <div className="grid grid-cols-[5rem_1fr] gap-2">
                <span className="t-text-dim">지금 ~ 6/14</span>
                <span className="t-text-sub">RVOL 분자 = volume_krx (KRX 단독), 분모 = avg20d (J→UN 점진 마이그레이션 중)</span>
              </div>
              <div className="grid grid-cols-[5rem_1fr] gap-2 pt-1.5" style={{ borderTop: "1px dashed var(--border-light)" }}>
                <span className="text-emerald-500 font-semibold">6/15+</span>
                <span className="t-text-sub">자동으로 volume (UN) 분자 전환 → 분자/분모 모두 UN으로 완벽 일치</span>
              </div>
            </div>
            <div className="mt-2 text-[10px] t-text-dim">
              ※ 마이그레이션 기간 중 RVOL이 점진적으로 약간 낮게 표시될 수 있습니다.
            </div>
          </div>
        </div>
      </div>,
      document.body
    )}
    {/* 30일 순위 설명 팝업 */}
    {showRank30Help && createPortal(
      <div className="fixed inset-0 z-[9999]" onClick={() => setShowRank30Help(false)}>
        <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
        <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[10000] w-[calc(100%-2rem)] max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl t-card border t-border-light p-5 anim-scale-in"
          onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-3">
            <span className="t-text font-semibold text-[15px] flex items-center gap-1.5">
              <BarChart3 size={14} className="text-orange-500" />
              30일 순위
            </span>
            <button onClick={() => setShowRank30Help(false)} className="p-1 t-text-dim hover:t-text transition" aria-label="닫기">
              <X size={16} />
            </button>
          </div>
          <div className="text-[12px] t-text-sub leading-relaxed mb-3">
            이 종목 자기 자신의 지난 30거래일 거래량 중 오늘의 위치 <span className="t-text-dim">(다른 종목과 비교 X)</span>.
            <br />
            <span className="t-text-dim text-[11px]">정규장 중: 오늘 거래량을 일중 추정치 <span className="font-mono">(현재 누적 × 390 / 경과분)</span>로 환산해 비교 — "예상 N위" 표기.</span>
          </div>
          <ul className="space-y-1.5 text-[11px] t-text-sub mb-3">
            <li><span className="text-red-500 font-semibold">1위</span> = 30일 중 거래량 최고 (역대급 이슈)</li>
            <li><span className="text-orange-500 font-semibold">상위 10%</span> — 매우 활발 (~3등 내)</li>
            <li><span className="t-text font-semibold">상위 50%</span> — 평소 수준</li>
            <li><span className="t-text-dim">상위 90%</span> — 매우 한산</li>
          </ul>
          <div className="rounded-lg border t-border-light p-3" style={{ background: "var(--bg)" }}>
            <div className="text-[11px] font-semibold t-text mb-1.5">💡 RVOL 함정 검증</div>
            <div className="text-[11px] t-text-sub leading-relaxed">
              RVOL +200%인데 30일 순위가 평범하면 → 20일 평균이 우연히 낮았던 것 (가짜).
              30일 순위도 상위면 진짜 폭증.
            </div>
          </div>
          {volume30dIsStale && (
            <div className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
              <div className="text-[11px] font-semibold text-amber-500 mb-1.5">⚠ 데이터 stale 경고</div>
              <div className="text-[11px] t-text-sub leading-relaxed">
                현재 30일 history는 <span className="font-mono">{volume30dSourceDate}</span> 기준 (<span className="font-semibold">{volume30dStaleDays}일 전</span>) 입니다.
                일봉 데이터 갱신 인프라가 일시적으로 멈춰있어 최근 거래 패턴이 반영되지 않았습니다.
                <br />
                → 표시되는 순위는 옛 데이터 대비 비교이므로 <span className="font-semibold">실제 의미와 다를 수 있습니다</span>.
                정상화 후 자동 활성화됩니다.
              </div>
            </div>
          )}
        </div>
      </div>,
      document.body
    )}
    {/* 거래 집중 설명 팝업 */}
    {showConcentrationHelp && createPortal(
      <div className="fixed inset-0 z-[9999]" onClick={() => setShowConcentrationHelp(false)}>
        <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
        <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[10000] w-[calc(100%-2rem)] max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl t-card border t-border-light p-5 anim-scale-in"
          onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-3">
            <span className="t-text font-semibold text-[15px] flex items-center gap-1.5">
              <BarChart3 size={14} className="text-emerald-500" />
              거래 집중 (가격대별 거래대금)
            </span>
            <button onClick={() => setShowConcentrationHelp(false)} className="p-1 t-text-dim hover:t-text transition" aria-label="닫기">
              <X size={16} />
            </button>
          </div>
          <div className="text-[12px] t-text-sub leading-relaxed mb-3">
            최근 분봉(약 30분)에서 가격대별 <span className="font-mono text-[11px] t-text-dim">(가격 × 체결량)</span> 합산 후 TOP3 가격 + 비중을 표시.
          </div>
          <ul className="space-y-1.5 text-[11px] t-text-sub mb-3">
            <li><span className="text-red-500 font-semibold">1순위(빨강)</span> — 거래대금이 가장 많이 발생한 가격대</li>
            <li>한 가격에 50%+ 집중 → 강한 매물대/지지선 또는 박스권 형성 신호</li>
            <li>여러 가격에 분산 → 가격 변동성 활발</li>
          </ul>
          <div className="rounded-lg border t-border-light p-3" style={{ background: "var(--bg)" }}>
            <div className="text-[11px] font-semibold t-text mb-1.5">💡 활용 팁</div>
            <div className="text-[11px] t-text-sub leading-relaxed">
              • 현재가가 1순위 가격 근처면 = 단기 균형점<br />
              • 현재가가 1순위 가격보다 위 → 매물 부담 가능성<br />
              • 휴장일/장 마감 후엔 마지막 분봉 1개에 집중되어 100% 표시
            </div>
          </div>
        </div>
      </div>,
      document.body
    )}
    {/* 포트폴리오 편집 모달 */}
    {showPortfolioEdit && (
      <div className="fixed inset-0 z-[60]" onClick={() => setShowPortfolioEdit(false)}>
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
        <div className="fixed bottom-0 left-0 right-0 z-[61] max-h-[85vh] overflow-y-auto rounded-t-2xl t-card border-t t-border-light p-5 sm:max-w-lg sm:mx-auto sm:rounded-2xl sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2 anim-slide-up sm:anim-scale-in"
          style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 2.5rem)' }} onClick={e => e.stopPropagation()}>
          {/* 드래그 핸들 + 닫기 */}
          <div className="flex items-center justify-center relative mb-3">
            <div className="w-8 h-1 rounded-full sm:hidden" style={{ background: 'var(--border)' }} />
            <button onClick={() => setShowPortfolioEdit(false)} className="absolute right-0 top-1/2 -translate-y-1/2 p-1 t-text-dim hover:t-text transition">
              <X size={18} />
            </button>
          </div>
          <h3 className="text-base font-bold t-text mb-4">포트폴리오 편집</h3>
          <div className="space-y-3 mb-4">
            {editHoldings.map((h: any, i: number) => (
              <div key={i} className="p-3 t-card-alt rounded-xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium t-text">{h.name} <span className="text-[10px] t-text-dim">{h.code}</span></span>
                  <button onClick={() => setEditHoldings(editHoldings.filter((_: any, j: number) => j !== i))}
                    className="text-xs text-red-400 hover:text-red-300">삭제</button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] t-text-dim block mb-0.5">평균단가</label>
                    <input type="number" value={h.avg_price || ""} onChange={e => { const v = [...editHoldings]; v[i] = {...h, avg_price: Number(e.target.value)}; setEditHoldings(v); }}
                      className="w-full text-[16px] p-1.5 rounded-lg t-card border t-border-light t-text" />
                  </div>
                  <div>
                    <label className="text-[10px] t-text-dim block mb-0.5">수량</label>
                    <input type="number" value={h.quantity || ""} onChange={e => { const v = [...editHoldings]; v[i] = {...h, quantity: Number(e.target.value)}; setEditHoldings(v); }}
                      className="w-full text-[16px] p-1.5 rounded-lg t-card border t-border-light t-text" />
                  </div>
                </div>
              </div>
            ))}
          </div>
          {/* 종목 검색 + 추가 (stock-master 2,618종목 + KIS API fallback) */}
          <div className="mb-4">
            <div className="relative">
              <input
                type="text"
                value={stockSearch}
                onChange={async (e) => {
                  const q = e.target.value;
                  setStockSearch(q);
                  if (q.length < 2) { setSearchResults([]); return; }
                  // stock-master.json 로드 (2,618종목)
                  let list = allStockList;
                  if (!list.length) {
                    setSearchLoading(true);
                    try {
                      const res = await fetch(import.meta.env.BASE_URL + "data/stock-master.json");
                      if (res.ok) {
                        const master = await res.json();
                        const stocks = (master?.stocks || []).map((s: any) => ({
                          code: s.code, name: s.name, market: s.market || "",
                        }));
                        setAllStockList(stocks);
                        list = stocks;
                      }
                    } catch {}
                    setSearchLoading(false);
                  }
                  // 로컬 검색 (종목명 또는 코드)
                  const results = list.filter((s: any) =>
                    s.name?.includes(q) || s.code?.includes(q)
                  ).slice(0, 10);
                  setSearchResults(results);
                  // 6자리 코드인데 결과 없으면 KIS API fallback
                  if (results.length === 0 && /^\d{6}$/.test(q) && supaUser) {
                    setSearchLoading(true);
                    try {
                      const kis = await searchKisStock(q);
                      if (kis) {
                        setSearchResults([{ code: kis.code, name: kis.name, market: "", current_price: kis.current_price, fromKis: true }]);
                      }
                    } catch {}
                    setSearchLoading(false);
                  }
                }}
                placeholder="종목명 또는 코드 검색 (2,618종목)..."
                className="w-full text-[16px] p-2.5 rounded-lg t-card border t-border-light t-text pr-8"
              />
              {searchLoading && <span className="absolute right-3 top-2.5 text-[10px] t-text-dim animate-pulse">검색 중...</span>}
            </div>
            {searchResults.length > 0 ? (
              <div className="mt-1 border t-border-light rounded-lg overflow-hidden max-h-48 overflow-y-auto">
                {searchResults.map((s: any, si: number) => (
                  <button key={si}
                    onClick={() => {
                      if (!editHoldings.find((h: any) => h.code === s.code)) {
                        const autoSector = (portfolio?.holdings || []).find((h: any) => h.code === s.code)?.sector || "";
                        setEditHoldings([...editHoldings, { name: s.name, code: s.code, sector: autoSector, avg_price: 0, quantity: 0 }]);
                      }
                      setStockSearch("");
                      setSearchResults([]);
                    }}
                    className="w-full text-left px-3 py-2 text-xs t-text hover:bg-blue-500/10 transition flex items-center justify-between border-b t-border-light last:border-b-0"
                  >
                    <div>
                      <span className="font-medium">{s.name}</span>
                      <span className="t-text-dim ml-1">{s.code}</span>
                      {s.market && <span className="t-text-dim ml-1 text-[10px]">{s.market}</span>}
                    </div>
                    <div className="flex items-center gap-1">
                      {s.current_price > 0 && <span className="t-text-dim">{s.current_price.toLocaleString()}원</span>}
                      {s.fromKis && <span className="text-[9px] px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-400">KIS</span>}
                    </div>
                  </button>
                ))}
              </div>
            ) : stockSearch.length >= 2 && !searchLoading && (
              <div className="mt-1 p-3 border t-border-light rounded-lg text-center">
                <div className="text-xs t-text-dim">검색 결과 없음</div>
                {/^\d{6}$/.test(stockSearch) ? (
                  supaUser
                    ? <div className="text-[10px] text-emerald-400 mt-1">KIS API로 실시간 조회 중...</div>
                    : <div className="text-[10px] t-text-dim mt-1">로그인하면 KIS API로 실시간 조회 가능</div>
                ) : (
                  <div className="text-[10px] t-text-dim mt-1">종목 코드 6자리 입력 시 KIS API로 실시간 조회합니다</div>
                )}
              </div>
            )}
          </div>
          {/* 저장 */}
          <button onClick={async () => {
            // DB 연동 (로그인 시)
            if (supaUser) {
              const prevCodes = new Set(dbHoldings.map(h => h.code));
              const newCodes = new Set(editHoldings.map((h: any) => h.code));
              // 삭제: DB에 있지만 편집본에 없는 것
              for (const prev of dbHoldings) {
                if (!newCodes.has(prev.code) && prev.id) {
                  await deleteHolding(prev.id);
                }
              }
              // 추가/수정
              for (const h of editHoldings) {
                const existing = dbHoldings.find(d => d.code === h.code);
                if (existing?.id) {
                  // 수정 (avg_price 또는 quantity 변경 시)
                  if (existing.avg_price !== h.avg_price || existing.quantity !== h.quantity) {
                    await updateHolding(existing.id, { avg_price: h.avg_price, quantity: h.quantity, name: h.name });
                  }
                } else {
                  // 신규 추가
                  await insertHolding(h);
                }
              }
              // DB에서 최신 데이터 리로드
              const fresh = await fetchHoldingsFromDB();
              setDbHoldings(fresh);
            }
            // localStorage 폴백 (항상 저장)
            localStorage.setItem("portfolio_holdings", JSON.stringify(editHoldings));
            // 화면 즉시 업데이트
            const totalInvested = editHoldings.reduce((s: number, h: any) => s + (h.avg_price || 0) * (h.quantity || 0), 0);
            const updated = editHoldings.map((h: any) => ({
              ...h,
              weight: totalInvested ? Math.round((h.avg_price || 0) * (h.quantity || 0) / totalInvested * 100) : 0,
              current_price: portfolio?.holdings?.find((ph: any) => ph.code === h.code)?.current_price || 0,
              profit_rate: (h.avg_price && portfolio?.holdings?.find((ph: any) => ph.code === h.code)?.current_price)
                ? Math.round(((portfolio.holdings.find((ph: any) => ph.code === h.code)?.current_price || 0) - h.avg_price) / h.avg_price * 10000) / 100 : 0,
              profit_amount: (h.avg_price && portfolio?.holdings?.find((ph: any) => ph.code === h.code)?.current_price)
                ? ((portfolio.holdings.find((ph: any) => ph.code === h.code)?.current_price || 0) - h.avg_price) * (h.quantity || 0) : 0,
              invested: (h.avg_price || 0) * (h.quantity || 0),
              current_value: (portfolio?.holdings?.find((ph: any) => ph.code === h.code)?.current_price || 0) * (h.quantity || 0),
              signal: portfolio?.holdings?.find((ph: any) => ph.code === h.code)?.signal || "분석 대상 외",
            }));
            const totalValue = updated.reduce((s: number, h: any) => s + h.current_value, 0);
            setPortfolio({
              ...portfolio,
              holdings: updated,
              summary: {
                total_invested: totalInvested,
                total_value: totalValue,
                total_profit_rate: totalInvested ? Math.round((totalValue - totalInvested) / totalInvested * 10000) / 100 : 0,
                total_profit_amount: totalValue - totalInvested,
                total_holdings: updated.length,
              },
            });
            setShowPortfolioEdit(false);
          }} className="w-full text-sm font-medium py-2.5 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition">
            {supaUser ? "저장" : "저장 (로컬)"}
          </button>
        </div>
      </div>
    )}
    {/* 종합 물타기 계산기 */}
    {showBulkAvgDown && createPortal(
      <div className="fixed inset-0 z-[9999] flex items-center justify-center anim-fade-in" onClick={() => setShowBulkAvgDown(false)}>
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
        <div className="relative z-10 mx-4 max-w-md w-full max-h-[80vh] flex flex-col rounded-2xl t-card border t-border-light" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between px-5 pt-5 pb-3 shrink-0">
            <h4 className="text-sm font-bold t-text">종합 물타기 계산기</h4>
            <button onClick={() => setShowBulkAvgDown(false)} className="t-text-dim hover:t-text transition"><X size={16} /></button>
          </div>
          <div className="flex-1 overflow-y-auto px-5 pb-5">
            {/* 종목별 입력 */}
            <div className="space-y-3 mb-4">
              {(portfolio?.holdings || []).filter((h: any) => !bulkExcluded.has(h.code)).map((h: any) => {
                const input = bulkInputs[h.code] || { price: "", qty: "" };
                return (
                  <div key={h.code} className="t-card-alt rounded-lg p-3 relative">
                    <button onClick={() => setBulkExcluded(prev => { const s = new Set(prev); s.add(h.code); return s; })}
                      className="absolute top-2 right-2 p-0.5 t-text-dim hover:t-text transition rounded-full hover:bg-black/5"><X size={14} /></button>
                    <div className="flex items-center justify-between mb-2 pr-5">
                      <div>
                        <span className="text-[12px] font-medium t-text">{h.name}</span>
                        <span className={`text-[10px] ml-1.5 font-medium ${profitColor(h.profit_rate)}`}>{h.profit_rate}%</span>
                      </div>
                      <div className="text-[9px] t-text-dim">평단 {(h.avg_price||0).toLocaleString()} × {h.quantity}주</div>
                    </div>
                    <div className="flex gap-2">
                      <input type="text" inputMode="numeric" value={input.price ? Number(input.price).toLocaleString() : ""} placeholder={`매수가 (${h.current_price?.toLocaleString() || ""})`}
                        onChange={e => { const v = e.target.value.replace(/[^0-9]/g, ""); setBulkInputs(prev => ({ ...prev, [h.code]: { ...input, price: v } })); }}
                        className="flex-1 px-2 py-1.5 rounded-lg text-[11px] t-text border t-border-light" style={{ background: "var(--bg)" }} />
                      <input type="text" inputMode="numeric" value={input.qty ? Number(input.qty).toLocaleString() : ""} placeholder="수량"
                        onChange={e => { const v = e.target.value.replace(/[^0-9]/g, ""); setBulkInputs(prev => ({ ...prev, [h.code]: { ...input, qty: v } })); }}
                        className="w-20 px-2 py-1.5 rounded-lg text-[11px] t-text border t-border-light" style={{ background: "var(--bg)" }} />
                    </div>
                  </div>
                );
              })}
            </div>
            {/* 종합 결과 */}
            {(() => {
              const holdings = (portfolio?.holdings || []).filter((h: any) => !bulkExcluded.has(h.code));
              let oldTotalInv = 0, oldTotalVal = 0, newTotalInv = 0, newTotalVal = 0, addTotalCost = 0;
              const details: { code: string; name: string; oldAvg: number; newAvg: number; newQty: number; oldPnl: number; newPnl: number }[] = [];
              for (const h of holdings) {
                const curAvg = h.avg_price || 0;
                const curQty = h.quantity || 0;
                const cp = h.current_price || 0;
                const input = bulkInputs[h.code] || { price: "", qty: "" };
                const addPrice = Number(input.price) || 0;
                const addQty = Number(input.qty) || 0;
                oldTotalInv += curAvg * curQty;
                oldTotalVal += cp * curQty;
                if (addPrice > 0 && addQty > 0) {
                  const newAvg = Math.round((curAvg * curQty + addPrice * addQty) / (curQty + addQty));
                  const newQty = curQty + addQty;
                  newTotalInv += newAvg * newQty;
                  newTotalVal += cp * newQty;
                  addTotalCost += addPrice * addQty;
                  const oldPnl = cp > 0 && curAvg > 0 ? (cp - curAvg) / curAvg * 100 : 0;
                  const newPnl = cp > 0 && newAvg > 0 ? (cp - newAvg) / newAvg * 100 : 0;
                  details.push({ code: h.code, name: h.name, oldAvg: curAvg, newAvg, newQty, oldPnl, newPnl });
                } else {
                  newTotalInv += curAvg * curQty;
                  newTotalVal += cp * curQty;
                }
              }
              if (!details.length) return <div className="text-[11px] t-text-dim text-center py-3">추가 매수 수량을 입력하세요</div>;
              const oldRate = oldTotalInv > 0 ? (oldTotalVal - oldTotalInv) / oldTotalInv * 100 : 0;
              const newRate = newTotalInv > 0 ? (newTotalVal - newTotalInv) / newTotalInv * 100 : 0;
              return (<>
                <div className="rounded-xl border t-border-light overflow-hidden">
                  {/* 수익률 */}
                  <div className="px-4 py-3.5 text-center border-b t-border-light" style={{ background: "var(--bg)" }}>
                    <div className="text-[10px] t-text-sub font-medium mb-1.5">총 수익률</div>
                    <div className="flex items-center justify-center gap-3">
                      <span className={`text-[15px] tabular-nums ${oldRate >= 0 ? "text-red-400" : "text-blue-400"}`}>{oldRate >= 0 ? "+" : ""}{oldRate.toFixed(2)}%</span>
                      <span className="text-sm t-text-dim">→</span>
                      <span className={`text-[22px] font-bold tabular-nums ${newRate >= 0 ? "text-red-500" : "text-blue-500"}`}>{newRate >= 0 ? "+" : ""}{newRate.toFixed(2)}%</span>
                    </div>
                  </div>
                  {/* 투자금 2열 */}
                  <div className="grid grid-cols-2 border-b t-border-light text-center">
                    <div className="py-2.5 border-r t-border-light">
                      <div className="text-[10px] t-text-sub">추가 투자금</div>
                      <div className="text-[12px] font-bold t-text tabular-nums mt-0.5">{addTotalCost.toLocaleString()}원</div>
                    </div>
                    <div className="py-2.5">
                      <div className="text-[10px] t-text-sub">총 투자금</div>
                      <div className="text-[12px] font-bold t-text tabular-nums mt-0.5">{(oldTotalInv + addTotalCost).toLocaleString()}원</div>
                    </div>
                  </div>
                  {/* 종목별 */}
                  {details.map((d, i) => (
                    <div key={d.name} className={`px-4 py-3 flex items-center justify-between ${i > 0 ? "border-t t-border-light" : ""}`}>
                      <div className="min-w-0">
                        <div className="text-[12px] font-semibold t-text">{d.name}</div>
                        <div className="text-[10px] t-text-sub tabular-nums mt-0.5">{d.oldAvg.toLocaleString()} → {d.newAvg.toLocaleString()}원</div>
                      </div>
                      <div className="flex items-center gap-1.5 tabular-nums shrink-0 ml-3">
                        <span className={`text-[11px] ${d.oldPnl >= 0 ? "text-red-400" : "text-blue-400"}`}>{d.oldPnl.toFixed(1)}%</span>
                        <span className="text-[10px] t-text-dim">→</span>
                        <span className={`text-[13px] font-bold ${d.newPnl >= 0 ? "text-red-500" : "text-blue-500"}`}>{d.newPnl.toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  onClick={async () => {
                    if (!window.confirm(`${details.length}건의 보유 종목 평단/수량을 업데이트합니다. 진행하시겠습니까?`)) return;
                    try {
                      await applyAvgDown(details.map(d => {
                        const input = bulkInputs[d.code] || { price: "", qty: "" };
                        const addP = Number(input.price) || 0;
                        const addQ = Number(input.qty) || 0;
                        return { code: d.code, newAvg: d.newAvg, newQty: d.newQty, addPrice: addP > 0 ? addP : undefined, addQty: addQ > 0 ? addQ : undefined };
                      }));
                      setShowBulkAvgDown(false);
                      setBulkInputs({});
                      setToastMsg(`물타기 반영 완료 — ${details.length}건`);
                      setTimeout(() => setToastMsg(""), 2500);
                    } catch {
                      setToastMsg("저장 실패");
                      setTimeout(() => setToastMsg(""), 3000);
                    }
                  }}
                  className="mt-3 w-full py-2.5 rounded-xl text-[12px] font-medium bg-blue-600 text-white hover:bg-blue-500 transition">
                  전체 반영 ({details.length}건)
                </button>
              </>);
            })()}
          </div>
        </div>
      </div>,
      document.body
    )}
    {/* 개별 물타기 계산기 (A/B/C 탭) */}
    {avgDownTarget && createPortal(
      <div className="fixed inset-0 z-[9999] flex items-center justify-center anim-fade-in" onClick={() => setAvgDownTarget(null)}>
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
        <div className="relative z-10 mx-6 max-w-sm w-full max-h-[85vh] flex flex-col rounded-2xl t-card border t-border-light" onClick={e => e.stopPropagation()}>
          <div className="px-5 pt-5 pb-0 shrink-0">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-bold t-text">물타기 계산기</h4>
              <button onClick={() => setAvgDownTarget(null)} className="t-text-dim hover:t-text transition"><X size={16} /></button>
            </div>
            {/* 현재 보유 */}
            <div className="t-card-alt rounded-lg p-3 mb-3">
              <div className="text-sm font-medium t-text mb-1">{avgDownTarget.name} <span className="text-[10px] t-text-dim">{avgDownTarget.code}</span></div>
              <div className="grid grid-cols-3 gap-2 text-[10px]">
                <div><span className="t-text-dim">평단가</span><div className="font-medium t-text">{(avgDownTarget.avg_price || 0).toLocaleString()}원</div></div>
                <div><span className="t-text-dim">수량</span><div className="font-medium t-text">{(avgDownTarget.quantity || 0).toLocaleString()}주</div></div>
                <div><span className="t-text-dim">현재가</span><div className="font-medium t-text">{(avgDownTarget.current_price || 0).toLocaleString()}원</div></div>
              </div>
            </div>
            {/* 탭 */}
            <div className="flex gap-1 mb-3">
              {([["basic","기본"],["target","목표 역산"],["multi","분할매수"]] as const).map(([k,l]) => (
                <button key={k} onClick={() => setAvgDownTab(k)}
                  className="flex-1 text-[10px] font-medium py-1.5 rounded-lg transition"
                  style={{ background: avgDownTab === k ? "var(--blue-600,#2563eb)" : "var(--bg-muted)", color: avgDownTab === k ? "#fff" : "var(--text-secondary)" }}>
                  {l}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-5 pb-5">
            {/* A: 기본 물타기 */}
            {avgDownTab === "basic" && (<>
              <div className="space-y-2 mb-3">
                <div>
                  <label className="text-[10px] t-text-dim mb-1 block">추가 매수가 (원)</label>
                  <input type="text" inputMode="numeric" value={avgDownPrice ? Number(avgDownPrice).toLocaleString() : ""} placeholder={avgDownTarget.current_price?.toLocaleString() || ""}
                    onChange={e => setAvgDownPrice(e.target.value.replace(/[^0-9]/g, ""))}
                    className="w-full px-3 py-2 rounded-lg text-sm t-text border t-border-light" style={{ background: "var(--bg)" }} />
                </div>
                <div>
                  <label className="text-[10px] t-text-dim mb-1 block">추가 수량 (주)</label>
                  <input type="text" inputMode="numeric" value={avgDownQty ? Number(avgDownQty).toLocaleString() : ""} placeholder="수량"
                    onChange={e => setAvgDownQty(e.target.value.replace(/[^0-9]/g, ""))}
                    className="w-full px-3 py-2 rounded-lg text-sm t-text border t-border-light" style={{ background: "var(--bg)" }} />
                </div>
              </div>
              {(() => {
                const curAvg = avgDownTarget.avg_price || 0, curQty = avgDownTarget.quantity || 0;
                const addP = Number(avgDownPrice) || 0, addQ = Number(avgDownQty) || 0;
                if (!addP || !addQ || !curAvg || !curQty) return null;
                const newAvg = Math.round((curAvg * curQty + addP * addQ) / (curQty + addQ));
                const cp = avgDownTarget.current_price || 0;
                const oldPnl = cp > 0 ? (cp - curAvg) / curAvg * 100 : 0;
                const newPnl = cp > 0 ? (cp - newAvg) / newAvg * 100 : 0;
                return (<>
                  <div className="t-card-alt rounded-lg p-3 space-y-2">
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div><span className="t-text-dim">새 평단가</span><div className="font-bold t-text text-sm">{newAvg.toLocaleString()}원</div></div>
                      <div><span className="t-text-dim">총 수량</span><div className="font-bold t-text text-sm">{(curQty + addQ).toLocaleString()}주</div></div>
                      <div><span className="t-text-dim">추가 투자금</span><div className="font-medium t-text">{(addP * addQ).toLocaleString()}원</div></div>
                      <div><span className="t-text-dim">총 투자금</span><div className="font-medium t-text">{(curAvg * curQty + addP * addQ).toLocaleString()}원</div></div>
                    </div>
                    <div className="border-t t-border-light pt-2 flex items-center justify-between text-[11px]">
                      <span className="t-text-dim">수익률</span>
                      <span>
                        <span className={oldPnl >= 0 ? "text-red-500" : "text-blue-500"}>{oldPnl >= 0 ? "+" : ""}{oldPnl.toFixed(2)}%</span>
                        <span className="t-text-dim mx-1">→</span>
                        <span className={`font-bold ${newPnl >= 0 ? "text-red-500" : "text-blue-500"}`}>{newPnl >= 0 ? "+" : ""}{newPnl.toFixed(2)}%</span>
                      </span>
                    </div>
                    {cp > 0 && newAvg > cp && (
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="t-text-dim">본전까지</span>
                        <span className="font-medium text-amber-500">+{((newAvg - cp) / cp * 100).toFixed(2)}% 상승 필요</span>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={async () => {
                      const confirmMsg = `평균단가 ${(curAvg).toLocaleString()}원 → ${newAvg.toLocaleString()}원\n수량 ${curQty.toLocaleString()}주 → ${(curQty + addQ).toLocaleString()}주\n\n매수 이력에 추가하고 포트폴리오를 갱신합니다. 계속할까요?`;
                      if (!window.confirm(confirmMsg)) return;
                      try {
                        await applyAvgDown([{ code: avgDownTarget.code, newAvg, newQty: curQty + addQ, addPrice: addP, addQty: addQ }]);
                        setAvgDownTarget(null);
                        setToastMsg(`${avgDownTarget.name} 반영 완료`);
                        setTimeout(() => setToastMsg(""), 2500);
                      } catch {
                        setToastMsg("저장 실패");
                        setTimeout(() => setToastMsg(""), 3000);
                      }
                    }}
                    className="mt-3 w-full py-2 rounded-xl text-[12px] font-medium bg-blue-600 text-white hover:bg-blue-500 transition">
                    포트폴리오에 반영
                  </button>
                </>);
              })()}
            </>)}
            {/* B: 목표 평균단가 역산 */}
            {avgDownTab === "target" && (<>
              <div className="space-y-2 mb-3">
                <div>
                  <label className="text-[10px] t-text-dim mb-1 block">목표 평균단가 (원)</label>
                  <input type="text" inputMode="numeric" value={targetAvg ? Number(targetAvg).toLocaleString() : ""} onChange={e => setTargetAvg(e.target.value.replace(/[^0-9]/g, ""))} placeholder="원하는 평균단가"
                    className="w-full px-3 py-2 rounded-lg text-sm t-text border t-border-light" style={{ background: "var(--bg)" }} />
                </div>
                <div className="flex gap-1 mb-1">
                  <button onClick={() => setTargetMode("qty")} className="flex-1 text-[10px] py-1 rounded-md transition"
                    style={{ background: targetMode === "qty" ? "var(--blue-600,#2563eb)" : "var(--bg-muted)", color: targetMode === "qty" ? "#fff" : "var(--text-secondary)" }}>
                    매수가 입력 → 수량 계산
                  </button>
                  <button onClick={() => setTargetMode("price")} className="flex-1 text-[10px] py-1 rounded-md transition"
                    style={{ background: targetMode === "price" ? "var(--blue-600,#2563eb)" : "var(--bg-muted)", color: targetMode === "price" ? "#fff" : "var(--text-secondary)" }}>
                    수량 입력 → 매수가 계산
                  </button>
                </div>
                <div>
                  <label className="text-[10px] t-text-dim mb-1 block">{targetMode === "qty" ? "매수 예정가 (원)" : "추가 수량 (주)"}</label>
                  <input type="text" inputMode="numeric" value={targetInput ? Number(targetInput).toLocaleString() : ""} onChange={e => setTargetInput(e.target.value.replace(/[^0-9]/g, ""))}
                    placeholder={targetMode === "qty" ? (avgDownTarget.current_price?.toString() || "") : "수량"}
                    className="w-full px-3 py-2 rounded-lg text-sm t-text border t-border-light" style={{ background: "var(--bg)" }} />
                </div>
              </div>
              {(() => {
                const curAvg = avgDownTarget.avg_price || 0, curQty = avgDownTarget.quantity || 0;
                const tAvg = Number(targetAvg) || 0;
                const inp = Number(targetInput) || (targetMode === "qty" ? (avgDownTarget.current_price || 0) : 0);
                if (!tAvg || !inp || !curAvg || !curQty || tAvg >= curAvg) return tAvg >= curAvg && tAvg > 0
                  ? <div className="text-[11px] text-amber-500 text-center py-2">목표 평단가는 현재 평단가({curAvg.toLocaleString()}원)보다 낮아야 합니다</div>
                  : null;
                if (targetMode === "qty") {
                  // 매수가(inp) → 필요 수량 계산: (curAvg*curQty + inp*X) / (curQty+X) = tAvg → X = curQty*(curAvg-tAvg)/(tAvg-inp)
                  if (inp >= tAvg) return <div className="text-[11px] text-amber-500 text-center py-2">매수 예정가가 목표 평단가보다 낮아야 합니다</div>;
                  const needQty = Math.ceil(curQty * (curAvg - tAvg) / (tAvg - inp));
                  const totalCost = inp * needQty;
                  const curInv = curAvg * curQty;
                  const ratio = totalCost / curInv;
                  return (
                    <div className="t-card-alt rounded-lg p-3 space-y-1 text-[11px]">
                      <div className="flex justify-between"><span className="t-text-dim">필요 수량</span><span className="font-bold t-text text-sm">{needQty.toLocaleString()}주</span></div>
                      <div className="flex justify-between"><span className="t-text-dim">추가 투자금</span><span className="font-medium t-text">{totalCost.toLocaleString()}원</span></div>
                      <div className="flex justify-between"><span className="t-text-dim">총 투자금</span><span className="font-medium t-text">{(curInv + totalCost).toLocaleString()}원</span></div>
                      <div className="flex justify-between"><span className="t-text-dim">총 수량</span><span className="font-medium t-text">{(curQty + needQty).toLocaleString()}주</span></div>
                      {ratio > 3 && (
                        <div className="text-[10px] text-amber-500 mt-1 pt-1 border-t t-border-light">
                          ⚠️ 추가 투자금이 현재 투자금의 {ratio.toFixed(1)}배입니다. 매수 예정가를 낮추거나 목표 평단가를 높여보세요.
                        </div>
                      )}
                    </div>
                  );
                } else {
                  // 수량(inp) → 필요 매수가 계산: (curAvg*curQty + X*inp) / (curQty+inp) = tAvg → X = (tAvg*(curQty+inp) - curAvg*curQty)/inp
                  const needPrice = Math.round((tAvg * (curQty + inp) - curAvg * curQty) / inp);
                  if (needPrice <= 0) return <div className="text-[11px] text-amber-500 text-center py-2">해당 수량으로는 목표 달성 불가</div>;
                  return (
                    <div className="t-card-alt rounded-lg p-3 space-y-1 text-[11px]">
                      <div className="flex justify-between"><span className="t-text-dim">필요 매수가</span><span className="font-bold t-text text-sm">{needPrice.toLocaleString()}원</span></div>
                      <div className="flex justify-between"><span className="t-text-dim">추가 투자금</span><span className="font-medium t-text">{(needPrice * inp).toLocaleString()}원</span></div>
                      <div className="flex justify-between"><span className="t-text-dim">총 투자금</span><span className="font-medium t-text">{(curAvg * curQty + needPrice * inp).toLocaleString()}원</span></div>
                      <div className="flex justify-between"><span className="t-text-dim">총 수량</span><span className="font-medium t-text">{(curQty + inp).toLocaleString()}주</span></div>
                    </div>
                  );
                }
              })()}
            </>)}
            {/* C: 다단계 분할매수 */}
            {avgDownTab === "multi" && (<>
              <div className="space-y-2 mb-3">
                {multiSteps.map((step, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-[10px] t-text-dim w-5 shrink-0">{i + 1}차</span>
                    <input type="text" inputMode="numeric" value={step.price ? Number(step.price).toLocaleString() : ""} placeholder="매수가"
                      onChange={e => { const v = e.target.value.replace(/[^0-9]/g, ""); const s = [...multiSteps]; s[i] = { ...s[i], price: v }; setMultiSteps(s); }}
                      className="flex-1 px-2 py-1.5 rounded-lg text-[11px] t-text border t-border-light" style={{ background: "var(--bg)" }} />
                    <input type="text" inputMode="numeric" value={step.qty ? Number(step.qty).toLocaleString() : ""} placeholder="수량"
                      onChange={e => { const v = e.target.value.replace(/[^0-9]/g, ""); const s = [...multiSteps]; s[i] = { ...s[i], qty: v }; setMultiSteps(s); }}
                      className="w-20 px-2 py-1.5 rounded-lg text-[11px] t-text border t-border-light" style={{ background: "var(--bg)" }} />
                    {multiSteps.length > 1 && (
                      <button onClick={() => setMultiSteps(s => s.filter((_, j) => j !== i))} className="t-text-dim hover:t-text"><X size={12} /></button>
                    )}
                  </div>
                ))}
                <button onClick={() => setMultiSteps(s => [...s, { price: "", qty: "" }])}
                  className="w-full text-[10px] py-1.5 rounded-lg border border-dashed t-border-light t-text-dim hover:t-text transition">
                  + 단계 추가
                </button>
              </div>
              {(() => {
                const curAvg = avgDownTarget.avg_price || 0, curQty = avgDownTarget.quantity || 0;
                const cp = avgDownTarget.current_price || 0;
                if (!curAvg || !curQty) return null;
                let runAvg = curAvg, runQty = curQty, runCost = curAvg * curQty;
                const rows: { step: number; price: number; qty: number; avg: number; totalQty: number; totalCost: number; pnl: number }[] = [];
                for (const step of multiSteps) {
                  const p = Number(step.price) || 0, q = Number(step.qty) || 0;
                  if (!p || !q) continue;
                  runCost += p * q;
                  runQty += q;
                  runAvg = Math.round(runCost / runQty);
                  rows.push({ step: rows.length + 1, price: p, qty: q, avg: runAvg, totalQty: runQty, totalCost: runCost, pnl: cp > 0 ? (cp - runAvg) / runAvg * 100 : 0 });
                }
                if (!rows.length) return null;
                const lastRow = rows[rows.length - 1];
                return (<>
                  <div className="t-card-alt rounded-lg p-3">
                    <div className="text-[10px] t-text-dim mb-2">단계별 결과</div>
                    <div className="space-y-1.5">
                      {rows.map(r => (
                        <div key={r.step} className="flex items-center justify-between text-[11px] pb-1.5 border-b t-border-light last:border-0">
                          <div>
                            <span className="font-medium t-text">{r.step}차</span>
                            <span className="t-text-dim ml-1">{r.price.toLocaleString()}원 × {r.qty}주</span>
                          </div>
                          <div className="text-right">
                            <div className="font-bold t-text">{r.avg.toLocaleString()}원</div>
                            <div className={`text-[10px] ${r.pnl >= 0 ? "text-red-500" : "text-blue-500"}`}>{r.pnl >= 0 ? "+" : ""}{r.pnl.toFixed(2)}%</div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="border-t t-border-light pt-2 mt-2 grid grid-cols-2 gap-2 text-[10px]">
                      <div><span className="t-text-dim">총 추가 투자</span><div className="font-medium t-text">{(lastRow.totalCost - curAvg * curQty).toLocaleString()}원</div></div>
                      <div><span className="t-text-dim">총 투자금</span><div className="font-medium t-text">{lastRow.totalCost.toLocaleString()}원</div></div>
                      {cp > 0 && lastRow.avg > cp && (
                        <div className="col-span-2"><span className="t-text-dim">본전까지</span> <span className="font-medium text-amber-500">+{((lastRow.avg - cp) / cp * 100).toFixed(2)}% 상승 필요</span></div>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={async () => {
                      const addedQty = lastRow.totalQty - curQty;
                      const addedCost = lastRow.totalCost - curAvg * curQty;
                      const addedAvgPrice = addedQty > 0 ? Math.round(addedCost / addedQty) : 0;
                      const confirmMsg = `평균단가 ${curAvg.toLocaleString()}원 → ${lastRow.avg.toLocaleString()}원\n수량 ${curQty.toLocaleString()}주 → ${lastRow.totalQty.toLocaleString()}주\n\n매수 이력에 추가하고 포트폴리오를 갱신합니다. 계속할까요?`;
                      if (!window.confirm(confirmMsg)) return;
                      try {
                        await applyAvgDown([{ code: avgDownTarget.code, newAvg: lastRow.avg, newQty: lastRow.totalQty, addPrice: addedAvgPrice, addQty: addedQty }]);
                        setAvgDownTarget(null);
                        setToastMsg(`${avgDownTarget.name} 반영 완료`);
                        setTimeout(() => setToastMsg(""), 2500);
                      } catch {
                        setToastMsg("저장 실패");
                        setTimeout(() => setToastMsg(""), 3000);
                      }
                    }}
                    className="mt-3 w-full py-2 rounded-xl text-[12px] font-medium bg-blue-600 text-white hover:bg-blue-500 transition">
                    포트폴리오에 반영
                  </button>
                </>);
              })()}
            </>)}
          </div>
        </div>
      </div>,
      document.body
    )}
  </>);
}
