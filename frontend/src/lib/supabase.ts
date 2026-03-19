import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = "https://fyklcplybyfrfryopzvx.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ5a2xjcGx5YnlmcmZyeW9wenZ4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk2MDIxMzIsImV4cCI6MjA4NTE3ODEzMn0.tih-g2tQRgL1e8Dtm0OWZU7Jdd5T0mC05TXD-C_CYGE";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
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
