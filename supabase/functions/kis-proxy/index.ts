import { createClient } from "https://esm.sh/@supabase/supabase-js@2"
import { corsHeaders } from "../_shared/cors.ts"

const KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"

interface KisCredentials {
  appKey: string
  appSecret: string
  accessToken: string
}

async function getKisCredentials(supabaseServiceClient: ReturnType<typeof createClient>): Promise<KisCredentials> {
  const { data, error } = await supabaseServiceClient
    .from("api_credentials")
    .select("credential_type, credential_value, expires_at")
    .eq("service_name", "kis")
    .eq("is_active", true)

  if (error || !data) throw new Error("KIS credentials not found")

  const creds: Record<string, string> = {}
  let tokenData: { access_token?: string } = {}

  for (const row of data) {
    if (row.credential_type === "access_token") {
      try {
        tokenData = JSON.parse(row.credential_value)
      } catch {
        // JSON이 아닌 경우 JWT 문자열 직접 사용
        if (row.credential_value && row.credential_value.startsWith("eyJ")) {
          tokenData = { access_token: row.credential_value }
        } else {
          tokenData = {}
        }
      }
    } else {
      creds[row.credential_type] = row.credential_value
    }
  }

  if (!creds.app_key || !creds.app_secret) {
    throw new Error("KIS app_key or app_secret missing")
  }
  if (!tokenData.access_token) {
    throw new Error("KIS access_token missing — run Python backend first to issue token")
  }

  return {
    appKey: creds.app_key,
    appSecret: creds.app_secret,
    accessToken: tokenData.access_token,
  }
}

function kisHeaders(creds: KisCredentials, trId: string): Record<string, string> {
  return {
    "Content-Type": "application/json; charset=utf-8",
    "authorization": `Bearer ${creds.accessToken}`,
    "appkey": creds.appKey,
    "appsecret": creds.appSecret,
    "tr_id": trId,
    "custtype": "P",
  }
}

async function fetchStockPrice(creds: KisCredentials, code: string): Promise<{ price: Record<string, unknown> | null; errorMsg: string | null }> {
  // UN(KRX+NXT 통합) — VWAP, 현재가, 등락률 등에 사용
  const urlUn = `${KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price?FID_COND_MRKT_DIV_CODE=UN&FID_INPUT_ISCD=${code}`
  const res = await fetch(urlUn, { headers: kisHeaders(creds, "FHKST01010100") })
  const data = await res.json()

  if (data.rt_cd !== "0") {
    return { price: null, errorMsg: data.msg1 || `rt_cd=${data.rt_cd}` }
  }
  const o = data.output

  // J(KRX 단독) — RVOL 분자(KRX-only volume)용. 일봉 평균과 시장 범위 일치(20일 평균은 KRX 일봉 기준).
  // 호출 실패 시 UN 값으로 fallback.
  let volumeKrx = parseInt(o.acml_vol) || 0
  try {
    const urlJ = `${KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price?FID_COND_MRKT_DIV_CODE=J&FID_INPUT_ISCD=${code}`
    const resJ = await fetch(urlJ, { headers: kisHeaders(creds, "FHKST01010100") })
    const dataJ = await resJ.json()
    if (dataJ.rt_cd === "0" && dataJ.output) {
      volumeKrx = parseInt(dataJ.output.acml_vol) || volumeKrx
    }
  } catch { /* fallback to UN volume */ }

  return {
    price: {
      code,
      name: o.hts_kor_isnm || "",
      current_price: parseInt(o.stck_prpr) || 0,
      change_rate: parseFloat(o.prdy_ctrt) || 0,
      change_amount: parseInt(o.prdy_vrss) || 0,
      volume: parseInt(o.acml_vol) || 0,
      volume_krx: volumeKrx,  // RVOL 분자 (KRX 단독, daily_ohlcv UN 마이그레이션 완료 시 frontend가 volume 사용으로 자동 전환)
      trading_value: parseInt(o.acml_tr_pbmn) || 0,  // 누적 거래대금 (VWAP 계산용)
      market_cap: parseInt(o.hts_avls) || 0,  // 시가총액(억)
      w52_hgpr: parseInt(o.stck_dryy_hgpr) || 0,
      w52_lwpr: parseInt(o.stck_dryy_lwpr) || 0,
      per: parseFloat(o.per) || 0,
      pbr: parseFloat(o.pbr) || 0,
    },
    errorMsg: null,
  }
}

function round2(v: number): number { return Math.round(v * 100) / 100 }

Deno.serve(async (req) => {
  // CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders })
  }

  try {
    // Verify caller identity (Authorization header or apikey header)
    const authHeader = req.headers.get("Authorization")
    const apiKey = req.headers.get("apikey")
    if (!authHeader && !apiKey) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      })
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!
    const supabaseAnonKey = Deno.env.get("SUPABASE_ANON_KEY")!
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!

    // Parse request
    const body = await req.json()
    const action = body.action as string
    const codes = (body.codes as string[]) || []

    // Service client for reading credentials
    const serviceClient = createClient(supabaseUrl, supabaseServiceKey)

    let result: Record<string, unknown> = {}

    // --- GitHub 알림 토글 (KIS credentials 불필요) ---
    if (action === "get-notify-settings") {
      const GITHUB_REPO = "xxonbang/theme-analyzer"
      const { data: ghCreds } = await serviceClient.table("api_credentials").select("credential_value").eq("service_name", "github").eq("credential_type", "pat").eq("is_active", true).single()
      if (!ghCreds) throw new Error("GitHub PAT not found in DB")
      const vars = ["TELEGRAM_NOTIFY", "TELEGRAM_MARKET_CLOSE", "TELEGRAM_FAILURE"]
      const settings: Record<string, boolean> = {}
      for (const v of vars) {
        const res = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/actions/variables/${v}`, {
          headers: { Authorization: `Bearer ${ghCreds.credential_value}`, Accept: "application/vnd.github+json" },
        })
        if (res.ok) {
          const d = await res.json()
          settings[v] = d.value !== "false"
        } else {
          settings[v] = true
        }
      }
      result = { settings }

    } else if (action === "set-notify-setting") {
      const key = body.key as string
      const enabled = body.enabled === true
      const ALLOWED = ["TELEGRAM_NOTIFY", "TELEGRAM_MARKET_CLOSE", "TELEGRAM_FAILURE"]
      if (!ALLOWED.includes(key)) throw new Error("Invalid setting key")
      const GITHUB_REPO = "xxonbang/theme-analyzer"
      const { data: ghCreds } = await serviceClient.table("api_credentials").select("credential_value").eq("service_name", "github").eq("credential_type", "pat").eq("is_active", true).single()
      if (!ghCreds) throw new Error("GitHub PAT not found in DB")
      const ghRes = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/actions/variables/${key}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${ghCreds.credential_value}`, Accept: "application/vnd.github+json" },
        body: JSON.stringify({ value: enabled ? "true" : "false" }),
      })
      result = { ok: ghRes.status === 204, key, enabled }

    // 하위 호환: 기존 get-notify / set-notify
    } else if (action === "get-notify") {
      const GITHUB_REPO = "xxonbang/theme-analyzer"
      const { data: ghCreds } = await serviceClient.table("api_credentials").select("credential_value").eq("service_name", "github").eq("credential_type", "pat").eq("is_active", true).single()
      if (!ghCreds) throw new Error("GitHub PAT not found in DB")
      const ghRes = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/actions/variables/TELEGRAM_NOTIFY`, {
        headers: { Authorization: `Bearer ${ghCreds.credential_value}`, Accept: "application/vnd.github+json" },
      })
      result = { enabled: ghRes.ok ? (await ghRes.json()).value === "true" : false }

    } else if (action === "set-notify") {
      const enabled = body.enabled === true
      const GITHUB_REPO = "xxonbang/theme-analyzer"
      const { data: ghCreds } = await serviceClient.table("api_credentials").select("credential_value").eq("service_name", "github").eq("credential_type", "pat").eq("is_active", true).single()
      if (!ghCreds) throw new Error("GitHub PAT not found in DB")
      const ghRes = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/actions/variables/TELEGRAM_NOTIFY`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${ghCreds.credential_value}`, Accept: "application/vnd.github+json" },
        body: JSON.stringify({ value: enabled ? "true" : "false" }),
      })
      result = { ok: ghRes.status === 204, enabled }

    } else if (action === "prices" && codes.length > 0) {
      const creds = await getKisCredentials(serviceClient)
      // Bulk price lookup (max 50 codes per request)
      const limited = codes.slice(0, 50)
      const prices: Record<string, unknown> = {}
      let lastError: string | null = null

      for (const code of limited) {
        const { price, errorMsg } = await fetchStockPrice(creds, code)
        if (price) prices[code] = price
        else if (errorMsg) lastError = errorMsg
        // Rate limit: 150ms between requests (KIS 모의투자 초당 제한 대응)
        if (limited.indexOf(code) < limited.length - 1) {
          await new Promise(r => setTimeout(r, 150))
        }
      }

      // 실패 종목 1회 재시도
      const failedCodes = limited.filter(c => !prices[c])
      if (failedCodes.length > 0 && failedCodes.length < limited.length) {
        for (const code of failedCodes) {
          await new Promise(r => setTimeout(r, 200))
          const { price, errorMsg } = await fetchStockPrice(creds, code)
          if (price) prices[code] = price
          else if (errorMsg) lastError = errorMsg
        }
      }
      // 전체 조회 실패 시 에러 반환 (토큰 만료 등)
      if (Object.keys(prices).length === 0 && limited.length > 0) {
        return new Response(JSON.stringify({ error: lastError || "모든 종목 조회 실패" }), {
          status: 502,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        })
      }
      result = { prices, failed: limited.length - Object.keys(prices).length }

    } else if (action === "search" && body.code) {
      // Single stock search by code
      const creds = await getKisCredentials(serviceClient)
      const { price, errorMsg } = await fetchStockPrice(creds, body.code)
      if (!price && errorMsg) {
        return new Response(JSON.stringify({ error: errorMsg }), {
          status: 502,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        })
      }
      result = { stock: price }

    } else if (action === "exchange") {
      // 환율 조회: FX@KRW(USD/KRW), FX@JPY, FX@EUR, FX@CNY
      const creds = await getKisCredentials(serviceClient)
      const fxCodes = [
        { code: "FX@KRW", key: "USDKRW" },
        { code: "FX@JPY", key: "JPYUSD" },
        { code: "FX@EUR", key: "EURUSD" },
        { code: "FX@CNY", key: "CNYUSD" },
      ]
      const fxResult: Record<string, { price: number; prev: number; change: number; changeRate: number }> = {}

      for (const fx of fxCodes) {
        const today = new Date().toISOString().slice(0, 10).replace(/-/g, "")
        const url = `${KIS_BASE_URL}/uapi/overseas-price/v1/quotations/inquire-daily-chartprice?FID_COND_MRKT_DIV_CODE=X&FID_INPUT_ISCD=${fx.code}&FID_INPUT_DATE_1=${today}&FID_INPUT_DATE_2=${today}&FID_PERIOD_DIV_CODE=D`
        try {
          const res = await fetch(url, { headers: kisHeaders(creds, "FHKST03030100") })
          const data = await res.json()
          if (data.rt_cd === "0" && data.output1) {
            const o = data.output1
            const price = parseFloat(o.ovrs_nmix_prpr) || 0
            const prev = parseFloat(o.ovrs_nmix_prdy_clpr) || 0
            const change = parseFloat(o.ovrs_nmix_prdy_vrss) || 0
            const changeRate = parseFloat(o.prdy_ctrt) || 0
            if (price > 0) {
              fxResult[fx.key] = { price, prev, change, changeRate }
            }
          }
        } catch { /* skip */ }
        await new Promise(r => setTimeout(r, 60))
      }

      // 교차환산: JPY(100)/KRW, EUR/KRW, CNY/KRW
      const usdkrw = fxResult.USDKRW?.price || 0
      const rates: Record<string, { rate: number; change: number; changeRate: number }> = {}
      if (usdkrw > 0) {
        rates.USD = { rate: round2(usdkrw), change: round2(fxResult.USDKRW?.change || 0), changeRate: round2(fxResult.USDKRW?.changeRate || 0) }
        if (fxResult.JPYUSD?.price) {
          const jpykrw = usdkrw / fxResult.JPYUSD.price * 100
          const prevJpykrw = (fxResult.USDKRW?.prev || usdkrw) / (fxResult.JPYUSD?.prev || fxResult.JPYUSD.price) * 100
          rates.JPY = { rate: round2(jpykrw), change: round2(jpykrw - prevJpykrw), changeRate: round2((jpykrw - prevJpykrw) / prevJpykrw * 100) }
        }
        if (fxResult.EURUSD?.price) {
          const eurkrw = usdkrw * fxResult.EURUSD.price
          const prevEurkrw = (fxResult.USDKRW?.prev || usdkrw) * (fxResult.EURUSD?.prev || fxResult.EURUSD.price)
          rates.EUR = { rate: round2(eurkrw), change: round2(eurkrw - prevEurkrw), changeRate: round2((eurkrw - prevEurkrw) / prevEurkrw * 100) }
        }
        if (fxResult.CNYUSD?.price) {
          const cnykrw = usdkrw / fxResult.CNYUSD.price
          const prevCnykrw = (fxResult.USDKRW?.prev || usdkrw) / (fxResult.CNYUSD?.prev || fxResult.CNYUSD.price)
          rates.CNY = { rate: round2(cnykrw), change: round2(cnykrw - prevCnykrw), changeRate: round2((cnykrw - prevCnykrw) / prevCnykrw * 100) }
        }
      }
      result = { rates }

    } else {
      return new Response(JSON.stringify({ error: "Invalid action" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      })
    }

    return new Response(JSON.stringify(result), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    })

  } catch (e) {
    const message = e instanceof Error ? e.message : "Internal error"
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    })
  }
})
