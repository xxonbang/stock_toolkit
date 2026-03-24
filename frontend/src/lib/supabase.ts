import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = "https://fyklcplybyfrfryopzvx.supabase.co";
const SUPABASE_KEY = "sb_publishable_QwdLROqMGoagr4s63SuoCQ_gtrvTOJx";

// 모듈 레벨 access token — auth 상태 변경 시 직접 설정
let _accessToken: string | null = null;
export function setAccessToken(token: string | null) { _accessToken = token; }
export function getAccessToken() { return _accessToken; }

export const STORAGE_KEY = `sb-${new URL(SUPABASE_URL).hostname.split(".")[0]}-auth-token`;

export const supabase = createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    // navigator.locks 비활성화 — 강제 새로고침 시 lock hang 방지
    lock: async <R>(_name: string, _acquireTimeout: number, fn: () => Promise<R>): Promise<R> => await fn(),
  },
  global: {
    // PostgREST/Edge Functions 요청에 user JWT 직접 주입
    // (SDK가 publishable key를 Authorization에 넣는 문제 우회)
    fetch: (url, options = {}) => {
      const urlStr = typeof url === "string" ? url : url instanceof Request ? url.url : "";
      if ((urlStr.includes("/rest/v1/") || urlStr.includes("/functions/v1/")) && _accessToken) {
        const headers = new Headers(options?.headers);
        headers.set("Authorization", `Bearer ${_accessToken}`);
        options = { ...options, headers };
      }
      return fetch(url, options);
    },
  },
});

export interface KisStockPrice {
  code: string;
  name: string;
  current_price: number;
  change_rate: number;
  change_amount: number;
  volume: number;
  w52_hgpr: number;
  w52_lwpr: number;
  per: number;
  pbr: number;
}

/**
 * KIS API 실시간 시세 조회 (Edge Function 경유)
 */
export async function fetchKisPrices(codes: string[]): Promise<Record<string, KisStockPrice>> {
  if (!codes.length) return {};
  const { data, error } = await supabase.functions.invoke("kis-proxy", {
    body: { action: "prices", codes },
  });
  if (error) throw new Error(`KIS API 호출 실패: ${error.message}`);
  return (data?.prices as Record<string, KisStockPrice>) ?? {};
}

/**
 * KIS API 단일 종목 검색
 */
export async function searchKisStock(code: string): Promise<KisStockPrice | null> {
  if (!code || code.length !== 6 || !/^\d{6}$/.test(code)) return null;
  const { data, error } = await supabase.functions.invoke("kis-proxy", {
    body: { action: "search", code },
  });
  if (error) return null;
  return (data?.stock as KisStockPrice) ?? null;
}

// ========== 포트폴리오 CRUD (Supabase) ==========

export interface PortfolioHolding {
  id?: string;
  code: string;
  name: string;
  avg_price: number;
  quantity: number;
  sector?: string;
}

/** DB에서 보유 종목 조회 */
export async function fetchHoldingsFromDB(): Promise<PortfolioHolding[]> {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];
  const { data, error } = await supabase
    .from("portfolio_holdings")
    .select("id, code, name, avg_price, quantity")
    .eq("user_id", user.id)
    .order("added_at");
  if (error) { console.error("포트폴리오 조회 실패:", error.message); return []; }
  return (data || []) as PortfolioHolding[];
}

/** DB에 종목 추가 */
export async function insertHolding(h: PortfolioHolding): Promise<boolean> {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return false;
  const { error } = await supabase.from("portfolio_holdings").insert({
    user_id: user.id,
    code: h.code,
    name: h.name,
    avg_price: h.avg_price,
    quantity: h.quantity,
  });
  if (error) {
    if (error.code === "23505") { console.warn("중복 종목:", h.code); }
    else { console.error("종목 추가 실패:", error.message); }
    return false;
  }
  return true;
}

/** DB 종목 수정 */
export async function updateHolding(id: string, updates: Partial<PortfolioHolding>): Promise<boolean> {
  const { error } = await supabase.from("portfolio_holdings").update({
    ...updates,
    updated_at: new Date().toISOString(),
  }).eq("id", id);
  if (error) { console.error("종목 수정 실패:", error.message); return false; }
  return true;
}

/** DB 종목 삭제 */
export async function deleteHolding(id: string): Promise<boolean> {
  const { error } = await supabase.from("portfolio_holdings").delete().eq("id", id);
  if (error) { console.error("종목 삭제 실패:", error.message); return false; }
  return true;
}

// ========== 알림 설정 (alert_config) ==========

export type AlertMode = "all" | "portfolio_only" | "off";

/** 알림 모드 조회 */
export async function getAlertMode(): Promise<AlertMode> {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return "all";
  const { data } = await supabase
    .from("alert_config")
    .select("alert_mode")
    .eq("user_id", user.id)
    .maybeSingle();
  return (data?.alert_mode as AlertMode) || "all";
}

/** 알림 설정 변경 (모드 + 익절/손절/trailing stop) */
export async function setAlertConfig(updates: { alert_mode?: AlertMode; take_profit_pct?: number; stop_loss_pct?: number; trailing_stop_pct?: number; buy_signal_mode?: string }): Promise<boolean> {
  try {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return false;
    // 기존 설정 조회 후 병합 (부분 업데이트 지원)
    const { data: existing } = await supabase.from("alert_config")
      .select("alert_mode, take_profit_pct, stop_loss_pct, trailing_stop_pct, buy_signal_mode")
      .eq("user_id", user.id).maybeSingle();
    const merged: Record<string, any> = {
      user_id: user.id,
      alert_mode: updates.alert_mode ?? existing?.alert_mode ?? "all",
      take_profit_pct: updates.take_profit_pct ?? existing?.take_profit_pct ?? 7.0,
      stop_loss_pct: updates.stop_loss_pct ?? existing?.stop_loss_pct ?? -2.0,
      trailing_stop_pct: updates.trailing_stop_pct ?? existing?.trailing_stop_pct ?? -3.0,
      buy_signal_mode: updates.buy_signal_mode ?? existing?.buy_signal_mode ?? "and",
      updated_at: new Date().toISOString(),
    };
    const { error } = await supabase.from("alert_config").upsert(merged, { onConflict: "user_id" });
    if (error) { console.error("설정 변경 실패:", error.code, error.message, error.details); return false; }
    return true;
  } catch (e) {
    console.error("setAlertConfig 예외:", e);
    return false;
  }
}

/** 알림 모드 변경 (하위호환) */
export async function setAlertMode(mode: AlertMode): Promise<boolean> {
  return setAlertConfig({ alert_mode: mode });
}

/** 익절/손절/trailing stop 조회 */
export async function getTradePct(): Promise<{ take_profit: number; stop_loss: number; trailing_stop: number; buy_signal_mode: string }> {
  const defaults = { take_profit: 7.0, stop_loss: -2.0, trailing_stop: -3.0, buy_signal_mode: "and" };
  try {
    const { data } = await supabase
      .from("alert_config")
      .select("take_profit_pct, stop_loss_pct, trailing_stop_pct, buy_signal_mode")
      .limit(1)
      .maybeSingle();
    return {
      take_profit: data?.take_profit_pct ?? defaults.take_profit,
      stop_loss: data?.stop_loss_pct ?? defaults.stop_loss,
      trailing_stop: data?.trailing_stop_pct ?? defaults.trailing_stop,
      buy_signal_mode: data?.buy_signal_mode ?? defaults.buy_signal_mode,
    };
  } catch {
    return defaults;
  }
}
