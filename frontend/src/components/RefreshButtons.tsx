import { useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";

const CRONJOB_API_KEY = import.meta.env.VITE_CRONJOB_API_KEY || "";
const MANUAL_DATA_JOB = "7376450";
const MANUAL_FULL_JOB = "7376451";

async function triggerManualJob(jobId: string): Promise<boolean> {
  try {
    // Enable the job (schedule is every minute, so it runs within 60s)
    const res = await fetch(`https://api.cron-job.org/jobs/${jobId}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${CRONJOB_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ job: { enabled: true } }),
    });
    if (!res.ok) return false;

    // Disable after 90s to prevent repeated runs
    setTimeout(async () => {
      await fetch(`https://api.cron-job.org/jobs/${jobId}`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${CRONJOB_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ job: { enabled: false } }),
      });
    }, 90000);

    return true;
  } catch {
    return false;
  }
}

export default function RefreshButtons() {
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
        setTimeout(() => window.location.reload(), 150000);
      } else {
        setResult("요청 실패");
      }
    } catch {
      setResult("네트워크 오류");
    }
    setLoading(null);
    setTimeout(() => setResult(null), 8000);
  }

  if (!CRONJOB_API_KEY) return null;

  return (
    <>
      <div className="flex items-center gap-1.5 shrink-0">
        <button
          onClick={() => handleRefresh("data-only")}
          disabled={!!loading}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium t-text-sub t-card-alt hover:opacity-80 rounded-lg transition disabled:opacity-50 whitespace-nowrap"
          title="데이터만 갱신 (Gemini 미사용)"
        >
          <RefreshCw size={12} className={loading === "data-only" ? "animate-spin" : ""} />
          갱신
        </button>
        <button
          onClick={() => handleRefresh("full")}
          disabled={!!loading}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition disabled:opacity-50 whitespace-nowrap"
          title="데이터 갱신 + AI 브리핑 생성"
        >
          <Sparkles size={12} className={loading === "full" ? "animate-spin" : ""} />
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
