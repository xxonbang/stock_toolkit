import { useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";

const CRONJOB_API_KEY = import.meta.env.VITE_CRONJOB_API_KEY || "";
const DATA_ONLY_JOB_ID = "7375005";
const FULL_JOB_IDS = ["7375862", "7375863", "7375864", "7375865"];

async function triggerCronJob(jobId: string): Promise<boolean> {
  try {
    const res = await fetch(`https://api.cron-job.org/jobs/${jobId}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${CRONJOB_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ job: { enabled: true } }),
    });
    return res.ok;
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
      let ok: boolean;
      if (mode === "data-only") {
        ok = await triggerCronJob(DATA_ONLY_JOB_ID);
      } else {
        ok = await triggerCronJob(FULL_JOB_IDS[0]);
      }
      setResult(ok ? "갱신 요청 완료 (1~2분 후 반영)" : "요청 실패");
    } catch {
      setResult("네트워크 오류");
    }
    setLoading(null);
    setTimeout(() => setResult(null), 5000);
  }

  if (!CRONJOB_API_KEY) return null;

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <button
        onClick={() => handleRefresh("data-only")}
        disabled={!!loading}
        className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition disabled:opacity-50"
        title="데이터만 갱신 (Gemini 미사용)"
      >
        <RefreshCw size={12} className={loading === "data-only" ? "animate-spin" : ""} />
        갱신
      </button>
      <button
        onClick={() => handleRefresh("full")}
        disabled={!!loading}
        className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition disabled:opacity-50"
        title="데이터 갱신 + AI 브리핑 생성"
      >
        <Sparkles size={12} className={loading === "full" ? "animate-spin" : ""} />
        AI
      </button>
      {result && (
        <div className={`text-[11px] ${result.includes("완료") ? "text-green-600" : "text-red-500"}`}>
          {result}
        </div>
      )}
    </div>
  );
}
