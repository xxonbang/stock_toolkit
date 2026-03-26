import { useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";

const CRONJOB_API_KEY = import.meta.env.VITE_CRONJOB_API_KEY || "";
const MANUAL_DATA_JOB = "7376450";
const MANUAL_FULL_JOB = "7376451";

const RELOAD_TIMEOUT = 150000;     // 2.5분 — 페이지 자동 리로드
const BUTTON_COOLDOWN = 90000;     // 90초 — 버튼 비활성 유지
const JOB_DISABLE_TIMEOUT = 75000; // 75초 — Job 비활성화 타이머

async function disableJob(jobId: string) {
  try {
    await fetch(`https://api.cron-job.org/jobs/${jobId}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${CRONJOB_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ job: { enabled: false } }),
    });
  } catch {}
}

async function triggerManualJob(jobId: string): Promise<boolean> {
  try {
    // 1) 활성화 — cron이 1분 내 1회 실행
    const res = await fetch(`https://api.cron-job.org/jobs/${jobId}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${CRONJOB_API_KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify({ job: { enabled: true } }),
    });
    if (!res.ok) return false;

    // 2) 즉시 비활성화 예약 — 75초 후 (cron 1회 실행 보장 후 비활성화)
    setTimeout(() => disableJob(jobId), JOB_DISABLE_TIMEOUT);

    // 3) 안전장치: 페이지 이탈 시에도 비활성화
    const cleanup = () => disableJob(jobId);
    window.addEventListener("beforeunload", cleanup, { once: true });
    window.addEventListener("pagehide", cleanup, { once: true });
    // visibilitychange로 백그라운드 전환도 감지
    const onVisChange = () => { if (document.hidden) { disableJob(jobId); document.removeEventListener("visibilitychange", onVisChange); } };
    document.addEventListener("visibilitychange", onVisChange);
    // 75초 후 이벤트 리스너 정리
    setTimeout(() => {
      window.removeEventListener("beforeunload", cleanup);
      window.removeEventListener("pagehide", cleanup);
      document.removeEventListener("visibilitychange", onVisChange);
    }, JOB_DISABLE_TIMEOUT + 1000);

    return true;
  } catch {
    return false;
  }
}

export default function RefreshButtons({ menuMode }: { menuMode?: boolean } = {}) {
  const [loading, setLoading] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function handleRefresh(mode: "data-only" | "full") {
    if (loading) return;
    setLoading(mode);
    setResult(null);
    try {
      const jobId = mode === "data-only" ? MANUAL_DATA_JOB : MANUAL_FULL_JOB;
      const ok = await triggerManualJob(jobId);
      if (ok) {
        setResult("갱신 시작! 약 2분 후 자동 반영");
        // Auto-reload after 2.5 minutes
        setTimeout(() => window.location.reload(), RELOAD_TIMEOUT);
      } else {
        setResult("요청 실패");
      }
    } catch {
      setResult("네트워크 오류");
    }
    // 90초간 버튼 비활성 유지 (중복 트리거 방지)
    setTimeout(() => setLoading(null), BUTTON_COOLDOWN);
    setTimeout(() => setResult(null), 8000);
  }

  if (!CRONJOB_API_KEY) return null;

  if (menuMode) {
    return (
      <>
        <button
          onClick={() => handleRefresh("data-only")}
          disabled={!!loading}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 text-[13px] t-text hover:bg-blue-500/10 rounded-lg transition disabled:opacity-50"
        >
          <RefreshCw size={16} className={`t-text-sub ${loading === "data-only" ? "animate-spin" : ""}`} />
          데이터 새로고침
        </button>
        <button
          onClick={() => handleRefresh("full")}
          disabled={!!loading}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 text-[13px] t-text hover:bg-blue-500/10 rounded-lg transition disabled:opacity-50"
        >
          <Sparkles size={16} className={`text-blue-400 ${loading === "full" ? "animate-spin" : ""}`} />
          AI 분석 재실시
        </button>
        {result && (
          <div className="fixed top-16 left-1/2 -translate-x-1/2 z-50 animate-fade-in">
            <div className={`px-4 py-2 rounded-full text-xs font-medium shadow-lg ${result.includes("시작") ? "bg-green-500 text-white" : "bg-red-500 text-white"}`}>
              {result}
            </div>
          </div>
        )}
      </>
    );
  }

  return (
    <>
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => handleRefresh("data-only")}
          disabled={!!loading}
          className="flex items-center gap-0.5 px-1.5 py-1 text-[10px] font-medium t-text-sub t-card-alt hover:opacity-80 rounded-md transition disabled:opacity-50 whitespace-nowrap"
          title="데이터만 갱신 (Gemini 미사용)"
        >
          <RefreshCw size={10} className={loading === "data-only" ? "animate-spin" : ""} />
          갱신
        </button>
        <button
          onClick={() => handleRefresh("full")}
          disabled={!!loading}
          className="flex items-center gap-0.5 px-1.5 py-1 text-[10px] font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-md transition disabled:opacity-50 whitespace-nowrap"
          title="데이터 갱신 + AI 브리핑 생성"
        >
          <Sparkles size={10} className={loading === "full" ? "animate-spin" : ""} />
          AI
        </button>
      </div>
      {/* 토스트 — fixed로 헤더 레이아웃 영향 없음 */}
      {result && (
        <div className="fixed top-16 left-1/2 -translate-x-1/2 z-50 animate-fade-in">
          <div className={`px-4 py-2 rounded-full text-xs font-medium shadow-lg ${result.includes("시작") ? "bg-green-500 text-white" : "bg-red-500 text-white"}`}>
            {result}
          </div>
        </div>
      )}
    </>
  );
}
