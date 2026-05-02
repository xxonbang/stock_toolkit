import { createContext, useContext, useEffect, useRef, useState, useCallback, type ReactNode } from "react";
import type { User, Session } from "@supabase/supabase-js";
import { supabase, setAccessToken, STORAGE_KEY } from "./supabase";

interface AuthContextType {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signUp: (email: string, password: string) => Promise<{ error: string | null }>;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
}

const INACTIVITY_TIMEOUT_MS = 60 * 60 * 1000; // 1시간
const ACTIVITY_THROTTLE_MS = 30 * 1000;

// admin 계정은 비활성 자동 로그아웃 면제 (소스 hardcode — 1인 admin 운영 가정)
const ADMIN_EMAILS = ["mackulri@gmail.com"];

function isAdminUser(u: User | null): boolean {
  return !!u?.email && ADMIN_EMAILS.includes(u.email.toLowerCase());
}

const AuthContext = createContext<AuthContextType | null>(null);

/** localStorage 세션 파싱 — ExpireStorage 래핑과 raw 두 포맷 모두 지원 */
function readStoredSession(): Session | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return null;
    const raw = JSON.parse(stored);
    const sessionStr = raw?.value && raw?.__expire__ ? raw.value : stored;
    const parsed = typeof sessionStr === "string" ? JSON.parse(sessionStr) : raw;
    if (parsed?.user && parsed?.access_token) return parsed as Session;
    return null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const inactivityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastActivityRef = useRef<number>(Date.now());

  const resetInactivityTimer = useCallback(() => {
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
    inactivityTimerRef.current = setTimeout(() => {
      setSession(null);
      setUser(null);
      setAccessToken(null);
      localStorage.removeItem(STORAGE_KEY);
      supabase.auth.signOut().catch(() => {});
    }, INACTIVITY_TIMEOUT_MS);
  }, []);

  // 비활성 자동 로그아웃 — admin은 면제하여 항상 로그인 유지
  useEffect(() => {
    if (!user || isAdminUser(user)) {
      if (inactivityTimerRef.current) { clearTimeout(inactivityTimerRef.current); inactivityTimerRef.current = null; }
      return;
    }
    const handleActivity = () => {
      const now = Date.now();
      if (now - lastActivityRef.current > ACTIVITY_THROTTLE_MS) {
        lastActivityRef.current = now;
        resetInactivityTimer();
      }
    };
    const events = ["mousedown", "keydown", "scroll", "touchstart"];
    resetInactivityTimer();
    events.forEach(e => window.addEventListener(e, handleActivity, { passive: true }));
    return () => {
      events.forEach(e => window.removeEventListener(e, handleActivity));
      if (inactivityTimerRef.current) { clearTimeout(inactivityTimerRef.current); inactivityTimerRef.current = null; }
    };
  }, [user, resetInactivityTimer]);

  // 탭 복귀 시 세션 갱신
  useEffect(() => {
    if (!user) return;
    const handleVisibility = () => {
      if (document.visibilityState !== "visible") return;
      const timeout = new Promise<null>(resolve => setTimeout(() => resolve(null), 5000));
      Promise.race([
        supabase.auth.getSession().then(({ data: { session } }) => session),
        timeout,
      ]).then((session) => {
        if (session?.user) {
          setAccessToken(session.access_token ?? null);
        } else {
          const fallback = readStoredSession();
          if (fallback?.access_token) setAccessToken(fallback.access_token);
        }
      }).catch(() => {});
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [user]);

  // 초기 세션 복원 + auth 이벤트 구독
  useEffect(() => {
    const restored = readStoredSession();
    if (restored?.user) {
      setSession(restored);
      setUser(restored.user);
      setAccessToken(restored.access_token ?? null);
    }
    setLoading(false);

    const authed = { current: !!restored };
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") authed.current = true;
      if (event === "SIGNED_OUT") return;
      if (authed.current && !session?.user) return;
      if (session?.user) {
        setSession(session);
        setUser(session.user);
        setAccessToken(session.access_token ?? null);
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password });
    return { error: error?.message ?? null };
  };

  const signIn = async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) return { error: error.message };
    if (data?.session) {
      setSession(data.session);
      setUser(data.session.user);
      setAccessToken(data.session.access_token ?? null);
    }
    return { error: null };
  };

  const signOut = async () => {
    setSession(null);
    setUser(null);
    setAccessToken(null);
    localStorage.removeItem(STORAGE_KEY);
    await supabase.auth.signOut().catch(() => {});
  };

  return (
    <AuthContext.Provider value={{ user, session, loading, signUp, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
