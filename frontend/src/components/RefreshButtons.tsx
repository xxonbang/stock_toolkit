import { useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";

const GH_TOKEN = import.meta.env.VITE_GH_PAT || "";
const DISPATCH_URL =
  "https://api.github.com/repos/xxonbang/stock_toolkit/actions/workflows/deploy-pages.yml/dispatches";

async function triggerWorkflow(mode: "data-only" | "full") {
  const res = await fetch(DISPATCH_URL, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github.v3+json",
      Authorization: `Bearer ${GH_TOKEN}`,
      "Content-Type": "application/json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ ref: "main", inputs: { mode } }),
  });
  return res.status === 204;
}

export default function RefreshButtons() {
  const [loading, setLoading] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function handleRefresh(mode: "data-only" | "full") {
    if (loading) return;
    setLoading(mode);
    setResult(null);
    try {
      const ok = await triggerWorkflow(mode);
      setResult(ok ? "갱신 요청 완료 (1~2분 후 반영)" : "요청 실패");
    } catch {
      setResult("네트워크 오류");
    }
    setLoading(null);
    setTimeout(() => setResult(null), 4000);
  }

  if (!GH_TOKEN) return null;

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => handleRefresh("data-only")}
        disabled={!!loading}
        className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition disabled:opacity-50"
        title="데이터만 갱신 (Gemini 미사용)"
      >
        <RefreshCw size={13} className={loading === "data-only" ? "animate-spin" : ""} />
        데이터 갱신
      </button>
      <button
        onClick={() => handleRefresh("full")}
        disabled={!!loading}
        className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition disabled:opacity-50"
        title="데이터 갱신 + AI 브리핑 생성"
      >
        <Sparkles size={13} className={loading === "full" ? "animate-spin" : ""} />
        AI 갱신
      </button>
      {result && (
        <span className={`text-xs ${result.includes("완료") ? "text-green-600" : "text-red-500"}`}>
          {result}
        </span>
      )}
    </div>
  );
}
