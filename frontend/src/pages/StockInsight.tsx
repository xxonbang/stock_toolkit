import { useEffect, useState } from "react";
import { Newspaper, Globe, MapPin, Youtube, Loader2, TrendingUp, ExternalLink, ArrowUp, Clock, ChevronDown, Check, X } from "lucide-react";
import { dataService } from "../services/dataService";

type RelatedNews = {
  title: string;
  title_ko?: string;
  url: string;
  published_at?: string;
};

type RelatedVideo = {
  title: string;
  url: string;
  channel_name?: string;
  published_at?: string;
};

type Top3Entry = {
  name: string;
  reason?: string;
  outlook?: string;
  freq?: number;
  refs?: string[];
  us_news_refs?: number[];
  kr_news_refs?: number[];
  related_news?: RelatedNews[];
  related_videos?: RelatedVideo[];
  _weak_signal?: boolean;
};

type RawItem = {
  idx: number;
  title: string;
  title_ko?: string;
  body?: string;
  url: string;
  published_at?: string;
};

type RawVideo = {
  video_id: string;
  title: string;
  description?: string;
  channel_name: string;
  published_at: string;
  transcript?: string;
  url: string;
};

type RegionData = {
  // phase=2 (AI 분석 후)
  top3_sectors?: Top3Entry[];
  top3_stocks?: Top3Entry[];
  outlook?: any;
  collected?: { news: number };
  // phase=1 (수집만)
  news?: RawItem[];
};

type YoutubeData = {
  top3_sectors?: Top3Entry[];
  top3_stocks?: Top3Entry[];
  videos_collected?: number;
  // phase=1
  videos?: RawVideo[];
};

type NewsTop3Payload = {
  generated_at?: string;
  phase?: number;
  us?: RegionData;
  kr?: RegionData;
  youtube?: YoutubeData;
};

function freqOf(e: Top3Entry, region: "us" | "kr"): number {
  if (region === "us") return e.us_news_refs?.length || 0;
  return e.kr_news_refs?.length || 0;
}

function HistoryPicker({
  historyList, selectedKey, onChange, latestLabel,
}: {
  historyList: { filename: string; kst: string }[];
  selectedKey: string;
  onChange: (key: string) => void;
  latestLabel: string;
}) {
  const [open, setOpen] = useState(false);
  const items: { key: string; label: string }[] = [
    { key: "latest", label: `최신 · ${latestLabel}` },
    ...historyList.map((h) => ({ key: h.filename, label: h.kst })),
  ];
  const current = items.find((it) => it.key === selectedKey) || items[0];

  // 외부 클릭 닫기
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      const tgt = e.target as HTMLElement;
      if (!tgt.closest("[data-history-picker]")) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <div className="relative" data-history-picker>
      <button onClick={() => setOpen(!open)}
        className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-[12px] t-text transition ${open ? "" : "hover:opacity-90"}`}
        style={{
          background: "var(--bg-card)",
          border: `1px solid ${open ? "rgba(99,102,241,0.5)" : "var(--border)"}`,
          boxShadow: open ? "0 0 0 3px rgba(99,102,241,0.12)" : "none",
        }}>
        <Clock size={12} className="t-text-dim shrink-0" />
        <span className="flex-1 text-left truncate">{current.label}</span>
        <ChevronDown size={14} className={`t-text-dim shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute z-30 mt-1.5 w-full rounded-xl overflow-hidden anim-fade-in"
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            boxShadow: "0 8px 24px rgba(0,0,0,0.18)",
          }}>
          <div className="max-h-[280px] overflow-y-auto py-1">
            {items.map((it, i) => {
              const active = it.key === selectedKey;
              return (
                <button key={it.key}
                  onClick={() => { onChange(it.key); setOpen(false); }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-[12px] text-left transition ${active ? "" : "hover:bg-blue-500/5"}`}
                  style={{
                    background: active ? "rgba(99,102,241,0.08)" : "transparent",
                    color: active ? "var(--accent)" : "var(--text)",
                    borderTop: i > 0 ? "1px solid var(--border-light, var(--border))" : "none",
                  }}>
                  <span className="flex-1 truncate">{it.label}</span>
                  {active && <Check size={13} />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function stripIndexHints(reason: string): string {
  // "[미뉴스#3,#7,#12]" 같은 인덱스 표기 제거 (백엔드가 누락했을 경우 안전망)
  return reason
    .replace(/\[(미뉴스|한뉴스|미커뮤|한커뮤)[^\]]*\]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function MentionsModal({
  open, onClose, title, news, videos,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  news: RelatedNews[];
  videos: RelatedVideo[];
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);
  if (!open) return null;
  const total = news.length + videos.length;
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center backdrop-blur-sm"
      style={{ background: "rgba(0,0,0,0.55)" }}
      onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="w-full sm:max-w-xl min-h-[70vh] sm:min-h-0 max-h-[90vh] flex flex-col rounded-t-2xl sm:rounded-2xl shadow-2xl"
        style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
        <div className="flex justify-center pt-2 pb-1 sm:hidden">
          <div className="w-10 h-1 rounded-full" style={{ background: "var(--border)" }} aria-hidden />
        </div>
        <div className="flex items-center justify-between p-4 sticky top-0" style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-card)" }}>
          <div className="min-w-0">
            <div className="text-[11px] t-text-dim">언급 내역</div>
            <div className="text-[15px] font-bold t-text truncate">{title}</div>
            <div className="text-[11px] t-text-dim mt-0.5">총 {total}건 (뉴스 {news.length} · 영상 {videos.length})</div>
          </div>
          <button onClick={onClose} aria-label="닫기"
            className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center hover:opacity-80"
            style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
            <X size={16} className="t-text-sub" />
          </button>
        </div>
        <div className="overflow-y-auto p-3 space-y-2">
          {news.map((n, i) => (
            <a key={`n-${i}`} href={n.url} target="_blank" rel="noopener noreferrer"
              className="block rounded-lg p-2.5 transition hover:opacity-80"
              style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
              <div className="flex items-start gap-2">
                <span className="text-[10px] px-1.5 py-0.5 rounded shrink-0 mt-0.5 bg-blue-500/10 text-blue-400">뉴스</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] t-text leading-[1.5] line-clamp-2">{n.title}</div>
                  {n.title_ko && (
                    <div className="text-[12px] t-text-sub leading-[1.5] mt-0.5 line-clamp-2">↳ {n.title_ko}</div>
                  )}
                  <div className="flex items-center gap-1.5 mt-1 text-[10px] t-text-dim">
                    {n.published_at && <span>{n.published_at.slice(0, 16)}</span>}
                    <ExternalLink size={10} />
                  </div>
                </div>
              </div>
            </a>
          ))}
          {videos.map((v, i) => (
            <a key={`v-${i}`} href={v.url} target="_blank" rel="noopener noreferrer"
              className="block rounded-lg p-2.5 transition hover:opacity-80"
              style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
              <div className="flex items-start gap-2">
                <span className="text-[10px] px-1.5 py-0.5 rounded shrink-0 mt-0.5 bg-rose-500/10 text-rose-400">영상</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] t-text leading-[1.5] line-clamp-2">{v.title}</div>
                  <div className="flex items-center gap-1.5 mt-1 text-[10px] t-text-dim">
                    {v.channel_name && <span>{v.channel_name}</span>}
                    {v.published_at && <span>· {v.published_at.slice(0, 10)}</span>}
                    <ExternalLink size={10} />
                  </div>
                </div>
              </div>
            </a>
          ))}
          {total === 0 && (
            <div className="py-8 text-center text-[12px] t-text-dim">언급 내역이 비어 있습니다</div>
          )}
        </div>
      </div>
    </div>
  );
}

function EntryCard({ entry, region, kind }: { entry: Top3Entry; region: "us" | "kr" | "youtube"; kind: "sector" | "stock" }) {
  const [showModal, setShowModal] = useState(false);
  const [showNewsList, setShowNewsList] = useState(false);
  const news = entry.related_news || [];
  const videos = entry.related_videos || [];
  const totalMentions = news.length + videos.length;
  const f = totalMentions > 0
    ? totalMentions
    : region === "youtube" ? (entry.freq || entry.refs?.length || 0) : freqOf(entry, region);
  const cleanReason = entry.reason ? stripIndexHints(entry.reason) : "";

  return (
    <div className="rounded-xl p-4 space-y-2" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${kind === "sector" ? "bg-blue-500/10 text-blue-400" : "bg-emerald-500/10 text-emerald-400"}`}>
            {kind === "sector" ? "섹터" : "종목"}
          </span>
          <h4 className="text-[15px] font-bold t-text">{entry.name}</h4>
          {entry._weak_signal && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500" title="임계값 미달이지만 참고용으로 노출됩니다">
              약한 시그널
            </span>
          )}
        </div>
        {f > 0 && (
          totalMentions > 0 ? (
            <button onClick={() => setShowModal(true)}
              className="text-[11px] px-2 py-0.5 rounded-md t-text-sub hover:t-text transition whitespace-nowrap shrink-0"
              style={{ background: "var(--bg)", border: "1px solid var(--border)" }}
              aria-label={`${entry.name} 언급 ${f}건 보기`}>
              언급 {f}건 ▸
            </button>
          ) : (
            <span className="text-[11px] t-text-dim">언급 {f}건</span>
          )
        )}
      </div>

      {cleanReason && (
        <p className="text-[12px] t-text-sub leading-[1.6]">{cleanReason}</p>
      )}

      {entry.outlook && (
        <div className="rounded-lg p-2.5 mt-2" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
          <div className="flex items-center gap-1.5 mb-1">
            <TrendingUp size={11} className="t-text-dim" />
            <span className="text-[10px] font-medium t-text-dim">1주일 전망</span>
          </div>
          <p className="text-[12px] t-text leading-[1.6] whitespace-pre-wrap">{entry.outlook}</p>
        </div>
      )}

      {news.length > 0 && (
        <div className="pt-1">
          <button onClick={() => setShowNewsList(!showNewsList)}
            className="w-full flex items-center justify-center gap-1.5 text-[11px] t-text-dim hover:t-text-sub transition py-1.5 rounded-lg"
            style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
            <Newspaper size={11} />
            {showNewsList ? `근거 뉴스 접기 ▲` : `근거 뉴스 ${news.length}건 보기 ▼`}
          </button>
          {showNewsList && (
            <div className="space-y-1.5 mt-2">
              {news.map((n, i) => (
                <a key={i} href={n.url} target="_blank" rel="noopener noreferrer"
                  className="block rounded-lg p-2 transition hover:opacity-80"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                  <div className="text-[12px] t-text leading-[1.5] line-clamp-2">{n.title}</div>
                  {n.title_ko && (
                    <div className="text-[11px] t-text-sub leading-[1.5] mt-0.5 line-clamp-2">↳ {n.title_ko}</div>
                  )}
                  {n.published_at && (
                    <div className="text-[10px] t-text-dim mt-1 flex items-center gap-1">
                      <span>{n.published_at.slice(0, 16)}</span>
                      <ExternalLink size={9} />
                    </div>
                  )}
                </a>
              ))}
            </div>
          )}
        </div>
      )}

      <MentionsModal open={showModal} onClose={() => setShowModal(false)}
        title={entry.name} news={news} videos={videos} />
    </div>
  );
}

function fmtKstDate(s?: string): string {
  if (!s) return "";
  // "2026-04-29 12:30:00 KST" 또는 ISO 형식 모두 처리
  if (s.includes("KST")) return s.slice(0, 16);  // "YYYY-MM-DD HH:MM"
  try {
    const d = new Date(s);
    return d.toLocaleString("ko-KR", { timeZone: "Asia/Seoul", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
  } catch {
    return s.slice(0, 16);
  }
}

function hostFromUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function RawItemCard({ item, badge }: { item: RawItem; badge: string }) {
  const host = hostFromUrl(item.url);
  return (
    <a href={item.url} target="_blank" rel="noopener noreferrer"
      className="block rounded-xl p-3 transition hover:opacity-80"
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-start gap-2">
        <span className="text-[10px] px-1.5 py-0.5 rounded shrink-0 mt-0.5 bg-blue-500/10 text-blue-400">{badge}</span>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] t-text leading-[1.5] line-clamp-2">{item.title}</div>
          {item.title_ko && (
            <div className="text-[12px] t-text-sub leading-[1.5] mt-0.5 line-clamp-2">↳ {item.title_ko}</div>
          )}
          <div className="flex items-center gap-1.5 mt-1.5 text-[10px] t-text-dim">
            <span>{fmtKstDate(item.published_at)}</span>
            {host && <><span>·</span><span className="truncate max-w-[180px]">{host}</span></>}
            <ExternalLink size={10} className="shrink-0" />
          </div>
        </div>
      </div>
    </a>
  );
}

function RawVideoCard({ video }: { video: RawVideo }) {
  return (
    <a href={video.url} target="_blank" rel="noopener noreferrer"
      className="block rounded-xl p-3 transition hover:opacity-80"
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-start gap-2">
        <span className="text-[10px] px-1.5 py-0.5 rounded shrink-0 mt-0.5 bg-rose-500/10 text-rose-400">{video.channel_name}</span>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] t-text leading-[1.5] line-clamp-2">{video.title}</div>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-[10px] t-text-dim">{fmtKstDate(video.published_at)}</span>
            {video.transcript && video.transcript.length > 0 && (
              <span className="text-[10px] t-text-dim">자막 {video.transcript.length}자</span>
            )}
            <ExternalLink size={10} className="t-text-dim" />
          </div>
        </div>
      </div>
    </a>
  );
}

function SectionBlock({
  icon, label, color, region, sectors, stocks, news, footer, isPhase1,
}: {
  icon: React.ReactNode;
  label: string;
  color: string;
  region: "us" | "kr" | "youtube";
  sectors: Top3Entry[];
  stocks: Top3Entry[];
  news?: RawItem[];
  footer?: string;
  isPhase1?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasTop3 = sectors.length > 0 || stocks.length > 0;
  const hasRaw = (news?.length || 0) > 0;

  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <span className={color}>{icon}</span>
        <h2 className="text-[16px] font-bold t-text tracking-tight">{label}</h2>
        {footer && <span className="text-[11px] t-text-dim">{footer}</span>}
      </div>

      {hasTop3 ? (
        <>
          {sectors.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-[12px] font-semibold t-text-sub px-1">TOP3 섹터</h3>
              <div className="space-y-2">
                {sectors.slice(0, 3).map((e, i) => <EntryCard key={`${region}-sec-${i}`} entry={e} region={region} kind="sector" />)}
              </div>
            </div>
          )}
          {stocks.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-[12px] font-semibold t-text-sub px-1">TOP3 종목</h3>
              <div className="space-y-2">
                {stocks.slice(0, 3).map((e, i) => <EntryCard key={`${region}-stk-${i}`} entry={e} region={region} kind="stock" />)}
              </div>
            </div>
          )}
        </>
      ) : isPhase1 && hasRaw ? (
        <>
          {news && news.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-[12px] font-semibold t-text-sub px-1">뉴스 ({news.length}건)</h3>
              <div className="space-y-2">
                {(expanded ? news : news.slice(0, 10)).map((it) => <RawItemCard key={`${region}-n-${it.idx}`} item={it} badge="뉴스" />)}
              </div>
              {news.length > 10 && (
                <button onClick={() => setExpanded(!expanded)}
                  className="w-full text-[12px] t-text-dim hover:t-text-sub transition py-2 rounded-lg"
                  style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
                  {expanded ? "접기 ▲" : `+${news.length - 10}건 더 ▼`}
                </button>
              )}
            </div>
          )}
        </>
      ) : (
        <div className="rounded-xl p-6 text-center text-[12px] t-text-dim italic" style={{ background: "var(--bg-card)", border: "1px dashed var(--border)" }}>
          {isPhase1 ? "수집된 데이터가 없습니다" : "시그널 부족 — TOP3 임계값 미달 또는 데이터 부족"}
        </div>
      )}
    </section>
  );
}

export default function StockInsight() {
  const [data, setData] = useState<NewsTop3Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [historyList, setHistoryList] = useState<{ filename: string; kst: string }[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>("latest");

  // 최초 로드: latest + 인덱스
  useEffect(() => {
    Promise.all([
      dataService.getNewsTop3(),
      dataService.getNewsTop3Index(),
    ])
      .then(([d, idx]) => {
        setData(d || null);
        setHistoryList(idx?.history || []);
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  // 히스토리 선택 변경 시 해당 파일 fetch
  const onHistoryChange = (key: string) => {
    setSelectedKey(key);
    setLoading(true);
    const fetcher = key === "latest"
      ? dataService.getNewsTop3()
      : dataService.getNewsTop3At(key);
    fetcher
      .then((d: any) => setData(d || null))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    const onScroll = () => setShowScrollTop(window.scrollY > 300);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 t-text-sub">
        <Loader2 size={20} className="animate-spin mr-2" />
        <span className="text-[13px]">데이터 로딩 중...</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="px-4 py-12 text-center">
        <Newspaper size={32} className="mx-auto mb-3 t-text-dim" />
        <div className="text-[14px] font-semibold t-text mb-1">아직 리포트가 생성되지 않았습니다</div>
        <div className="text-[12px] t-text-dim">매일 KST 07:30, 20:00에 자동 갱신됩니다</div>
      </div>
    );
  }

  const us = data.us || {};
  const kr = data.kr || {};
  const yt = data.youtube || {};
  const isPhase1 = data.phase === 1;

  return (
    <div className="px-3 pt-3 pb-8 space-y-6 max-w-2xl mx-auto">
      {/* 헤더 */}
      <header className="space-y-2">
        <div className="flex items-center justify-between">
          <h1 className="text-[18px] font-bold t-text tracking-tight">Stock Insight</h1>
          {data.generated_at && (
            <span className="text-[11px] t-text-dim">{data.generated_at}</span>
          )}
        </div>
        <p className="text-[12px] t-text-sub">미국·한국 뉴스 + 유튜브 분석 기반 TOP3 섹터 · 종목 리포트</p>
        {historyList.length > 0 && (
          <HistoryPicker
            historyList={historyList}
            selectedKey={selectedKey}
            onChange={onHistoryChange}
            latestLabel={data.generated_at || "—"}
          />
        )}
      </header>

      {/* AI 분석 미실행 경고 (Phase 1 페이로드인 경우) */}
      {isPhase1 && (
        <div className="rounded-xl p-3 text-[12px] t-text-sub"
          style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.25)" }}>
          ⚠️ AI 분석이 실행되지 않은 수집 결과입니다. 다음 정기 실행(KST 07:30 또는 20:00) 후 TOP3·전망이 추가됩니다. 아래는 수집된 raw 데이터.
        </div>
      )}

      {/* 미국 */}
      <SectionBlock
        icon={<Globe size={16} />} label="미국 시장" color="text-blue-400"
        region="us"
        sectors={us.top3_sectors || []}
        stocks={us.top3_stocks || []}
        news={us.news}
        footer={isPhase1 && us.news ? `뉴스 ${us.news.length}건` : us.collected ? `뉴스 ${us.collected.news}건` : undefined}
        isPhase1={isPhase1}
      />

      {/* 한국 */}
      <SectionBlock
        icon={<MapPin size={16} />} label="한국 시장" color="text-emerald-400"
        region="kr"
        sectors={kr.top3_sectors || []}
        stocks={kr.top3_stocks || []}
        news={kr.news}
        footer={isPhase1 && kr.news ? `뉴스 ${kr.news.length}건` : kr.collected ? `뉴스 ${kr.collected.news}건` : undefined}
        isPhase1={isPhase1}
      />

      {/* 유튜브 — phase 1과 2 분기 */}
      {isPhase1 && yt.videos && yt.videos.length > 0 ? (
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-rose-400"><Youtube size={16} /></span>
            <h2 className="text-[16px] font-bold t-text tracking-tight">유튜브 트렌드</h2>
            <span className="text-[11px] t-text-dim">영상 {yt.videos.length}개 (최근 7일)</span>
          </div>
          <div className="space-y-2">
            {yt.videos.map((v) => <RawVideoCard key={v.video_id} video={v} />)}
          </div>
        </section>
      ) : (
        <SectionBlock
          icon={<Youtube size={16} />} label="유튜브 트렌드" color="text-rose-400"
          region="youtube"
          sectors={yt.top3_sectors || []}
          stocks={yt.top3_stocks || []}
          footer={yt.videos_collected != null ? `영상 ${yt.videos_collected}개 분석` : undefined}
          isPhase1={isPhase1}
        />
      )}

      {/* 푸터 */}
      <footer className="pt-4 text-[11px] t-text-dim text-center">
        Google News BUSINESS · Yahoo Finance · 네이버 금융 · YouTube Data API + Gemini 2.5 Flash Lite
      </footer>

      {/* 스크롤 최상단 floating 버튼 */}
      {showScrollTop && (
        <button onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          aria-label="맨 위로"
          className="fixed bottom-6 right-6 z-40 w-11 h-11 rounded-full flex items-center justify-center transition hover:scale-105 active:scale-95"
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            boxShadow: "0 4px 16px rgba(0,0,0,0.18)",
          }}>
          <ArrowUp size={18} className="t-text-sub" />
        </button>
      )}
    </div>
  );
}
