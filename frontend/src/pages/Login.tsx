import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { Loader2, LogIn, Mail, Lock, Ticket, TrendingUp } from "lucide-react";
import { useAuth } from "../lib/AuthContext";
import { supabase } from "../lib/supabase";

type Tab = "login" | "signup";

export default function Login() {
  const { user, loading: authLoading, signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [signUpSuccess, setSignUpSuccess] = useState(false);

  // 이미 로그인된 상태라면 루트로
  if (!authLoading && user) return <Navigate to="/" replace />;

  const switchTab = (t: Tab) => {
    setTab(t);
    setError("");
    setSignUpSuccess(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "login") {
        const { error: errMsg } = await signIn(email.trim(), password);
        if (errMsg) {
          setError(
            errMsg.includes("Invalid login") ? "이메일 또는 비밀번호가 올바르지 않습니다"
            : errMsg.includes("rate limit") ? "잠시 후 다시 시도해주세요"
            : errMsg,
          );
          return;
        }
        navigate("/", { replace: true });
      } else {
        // 회원가입 — 초대코드 검증 선행
        const { data: codes } = await supabase
          .from("invite_codes")
          .select("id")
          .eq("code", inviteCode.trim())
          .eq("is_active", true)
          .limit(1);
        if (!codes || codes.length === 0) {
          setError("유효하지 않은 가입코드입니다.");
          return;
        }
        const { error: errMsg } = await signUp(email.trim(), password);
        if (errMsg) {
          setError(errMsg);
          return;
        }
        setSignUpSuccess(true);
      }
    } catch (e: any) {
      setError(e?.message || "네트워크 오류. 다시 시도해주세요.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: "var(--bg)" }}>
      <div className="w-full max-w-[360px] space-y-6">
        {/* 로고 / 타이틀 */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl"
            style={{ background: "linear-gradient(135deg, rgba(59,130,246,0.15), rgba(168,85,247,0.12))", border: "1px solid rgba(99,102,241,0.25)" }}>
            <TrendingUp size={26} strokeWidth={2.25} className="text-blue-400" />
          </div>
          <h1 className="text-xl font-bold tracking-tight t-text">Stock Toolkit</h1>
          <p className="text-sm t-text-dim">AI 기반 종목 분석 및 자동매매</p>
        </div>

        {/* 탭 */}
        <div className="flex rounded-xl p-1 gap-1" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <button type="button" onClick={() => switchTab("login")}
            className={`flex-1 py-2 px-3 rounded-lg text-[13px] font-medium transition ${tab === "login" ? "bg-blue-600 text-white shadow-sm" : "t-text-dim hover:t-text"}`}>
            로그인
          </button>
          <button type="button" onClick={() => switchTab("signup")}
            className={`flex-1 py-2 px-3 rounded-lg text-[13px] font-medium transition ${tab === "signup" ? "bg-blue-600 text-white shadow-sm" : "t-text-dim hover:t-text"}`}>
            회원가입
          </button>
        </div>

        {/* 회원가입 성공 */}
        {signUpSuccess && (
          <div className="p-3 rounded-xl text-[13px] text-center"
            style={{ background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.25)", color: "rgb(34,197,94)" }}>
            회원가입 완료! 이메일을 확인하여 계정을 인증해주세요.
          </div>
        )}

        {/* 폼 */}
        {!signUpSuccess && (
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 t-text-dim" />
              <input type="email" placeholder="이메일" value={email} onChange={e => setEmail(e.target.value)}
                required autoComplete="email"
                className="w-full text-[14px] pl-10 pr-3.5 py-3 rounded-xl t-text outline-none"
                style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }} />
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 t-text-dim" />
              <input type="password" placeholder="비밀번호" value={password} onChange={e => setPassword(e.target.value)}
                required minLength={6} autoComplete={tab === "login" ? "current-password" : "new-password"}
                className="w-full text-[14px] pl-10 pr-3.5 py-3 rounded-xl t-text outline-none"
                style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }} />
            </div>
            {tab === "signup" && (
              <div className="relative">
                <Ticket className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 t-text-dim" />
                <input type="text" placeholder="가입코드" value={inviteCode} onChange={e => setInviteCode(e.target.value)}
                  required autoComplete="off"
                  className="w-full text-[14px] pl-10 pr-3.5 py-3 rounded-xl t-text outline-none"
                  style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }} />
              </div>
            )}

            {error && (
              <div className="p-3 rounded-xl text-[12px] text-center text-red-400"
                style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)" }}>
                {error}
              </div>
            )}

            <button type="submit" disabled={loading || !email.trim() || !password || (tab === "signup" && !inviteCode.trim())}
              className="w-full flex items-center justify-center gap-2 text-[14px] font-semibold py-3 rounded-xl text-white bg-blue-600 hover:bg-blue-500 transition disabled:opacity-40">
              {loading ? <Loader2 size={16} className="animate-spin" /> : <LogIn size={16} />}
              {loading ? (tab === "login" ? "로그인 중..." : "가입 중...") : (tab === "login" ? "로그인" : "회원가입")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
