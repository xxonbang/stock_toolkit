import { useEffect, useState } from "react";
import { Newspaper, Globe, MapPin, Youtube, Loader2, TrendingUp, ExternalLink } from "lucide-react";
import { dataService } from "../services/dataService";

type Top3Entry = {
  name: string;
  reason?: string;
  outlook?: string;
  freq?: number;
  refs?: string[];
  us_news_refs?: number[];
  us_community_refs?: number[];
  kr_news_refs?: number[];
  kr_community_refs?: number[];
};

type RawItem = {
  idx: number;
  title: string;
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
  collected?: { news: number; community: number };
  // phase=1 (수집만)
  news?: RawItem[];
  community?: RawItem[];
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
  if (region === "us") {
    return (e.us_news_refs?.length || 0) + (e.us_community_refs?.length || 0);
  }
  return (e.kr_news_refs?.length || 0) + (e.kr_community_refs?.length || 0);
}

function EntryCard({ entry, region, kind }: { entry: Top3Entry; region: "us" | "kr" | "youtube"; kind: "sector" | "stock" }) {
  const f = region === "youtube" ? (entry.freq || entry.refs?.length || 0) : freqOf(entry, region);
  return (
    <div className="rounded-xl p-4 space-y-2" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${kind === "sector" ? "bg-blue-500/10 text-blue-400" : "bg-emerald-500/10 text-emerald-400"}`}>
            {kind === "sector" ? "섹터" : "종목"}
          </span>
          <h4 className="text-[15px] font-bold t-text">{entry.name}</h4>
        </div>
        {f > 0 && (
          <span className="text-[11px] t-text-dim">언급 {f}건</span>
        )}
      </div>
      {entry.reason && (
        <p className="text-[12px] t-text-sub leading-[1.6]">{entry.reason}</p>
      )}
      {entry.outlook && (
        <div className="rounded-lg p-2.5 mt-2" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
          <div className="flex items-center gap-1.5 mb-1">
            <TrendingUp size={11} className="t-text-dim" />
            <span className="text-[10px] font-medium t-text-dim">1주일 전망</span>
          </div>
          <p className="text-[12px] t-text leading-[1.6]">{entry.outlook}</p>
        </div>
      )}
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

function RawItemCard({ item, badge }: { item: RawItem; badge: string }) {
  return (
    <a href={item.url} target="_blank" rel="noopener noreferrer"
      className="block rounded-xl p-3 transition hover:opacity-80"
      style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
      <div className="flex items-start gap-2">
        <span className="text-[10px] px-1.5 py-0.5 rounded shrink-0 mt-0.5 bg-blue-500/10 text-blue-400">{badge}</span>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] t-text leading-[1.5] line-clamp-2">{item.title}</div>
          {item.body && (
            <div className="text-[11px] t-text-dim leading-[1.5] mt-1 line-clamp-2">{item.body}</div>
          )}
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-[10px] t-text-dim">{fmtKstDate(item.published_at)}</span>
            <ExternalLink size={10} className="t-text-dim" />
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
  icon, label, color, region, sectors, stocks, news, community, footer, isPhase1,
}: {
  icon: React.ReactNode;
  label: string;
  color: string;
  region: "us" | "kr" | "youtube";
  sectors: Top3Entry[];
  stocks: Top3Entry[];
  news?: RawItem[];
  community?: RawItem[];
  footer?: string;
  isPhase1?: boolean;
}) {
  const hasTop3 = sectors.length > 0 || stocks.length > 0;
  const hasRaw = (news?.length || 0) + (community?.length || 0) > 0;

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
                {news.slice(0, 8).map((it) => <RawItemCard key={`${region}-n-${it.idx}`} item={it} badge="뉴스" />)}
              </div>
              {news.length > 8 && <div className="text-[11px] t-text-dim text-center pt-1">+{news.length - 8}건 더</div>}
            </div>
          )}
          {community && community.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-[12px] font-semibold t-text-sub px-1">커뮤니티 ({community.length}건)</h3>
              <div className="space-y-2">
                {community.slice(0, 8).map((it) => <RawItemCard key={`${region}-c-${it.idx}`} item={it} badge="커뮤" />)}
              </div>
              {community.length > 8 && <div className="text-[11px] t-text-dim text-center pt-1">+{community.length - 8}건 더</div>}
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

  useEffect(() => {
    dataService.getNewsTop3()
      .then((d: any) => setData(d || null))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
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
      <header className="space-y-1">
        <div className="flex items-center justify-between">
          <h1 className="text-[18px] font-bold t-text tracking-tight">Stock Insight</h1>
          {data.generated_at && (
            <span className="text-[11px] t-text-dim">{data.generated_at}</span>
          )}
        </div>
        <p className="text-[12px] t-text-sub">미국·한국 뉴스/커뮤니티/유튜브 분석 기반 TOP3 섹터 · 종목 리포트</p>
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
        community={us.community}
        footer={isPhase1 && us.news ? `뉴스 ${us.news.length} · 커뮤니티 ${us.community?.length || 0}` : us.collected ? `뉴스 ${us.collected.news} · 커뮤니티 ${us.collected.community}` : undefined}
        isPhase1={isPhase1}
      />

      {/* 한국 */}
      <SectionBlock
        icon={<MapPin size={16} />} label="한국 시장" color="text-emerald-400"
        region="kr"
        sectors={kr.top3_sectors || []}
        stocks={kr.top3_stocks || []}
        news={kr.news}
        community={kr.community}
        footer={isPhase1 && kr.news ? `뉴스 ${kr.news.length} · 커뮤니티 ${kr.community?.length || 0}` : kr.collected ? `뉴스 ${kr.collected.news} · 커뮤니티 ${kr.collected.community}` : undefined}
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
        Google News · Hacker News · StockTwits · FM코리아 · 클리앙 · YouTube Data API + Gemini 2.5 Flash Lite
      </footer>
    </div>
  );
}
