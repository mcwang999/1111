"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { ApiResponse, Document, Stats } from "@/lib/types";
import {
  AGENT_LABELS,
  BRIEFING_STATUS_LABELS,
  DOC_TYPE_LABELS,
  IMPACT_TAG_LABELS,
  REGION_LABELS,
  SIGNAL_TYPE_LABELS,
  TOPIC_LABELS,
  formatScore,
  formatShortDateTime,
  getBriefingStatus,
  getCardLastSeenAt,
  getCardPublishedAt,
  labelFor,
} from "@/lib/types";

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [cards, setCards] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [statsRes, cardsRes] = await Promise.all([
        fetch("/api/stats"),
        fetch("/api/documents?doc_type=cards&limit=8&sort=last_seen_at&dir=desc"),
      ]);
      if (!statsRes.ok) throw new Error("统计数据加载失败");
      if (!cardsRes.ok) throw new Error("情报卡片加载失败");

      const nextStats = (await statsRes.json()) as Stats;
      const nextCards = (await cardsRes.json()) as ApiResponse<Document>;
      setStats(nextStats);
      setCards(nextCards.data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadData]);

  if (loading) return <DashboardSkeleton />;
  if (error || !stats) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error || "加载失败"}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-b border-neutral-200 pb-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-medium uppercase text-neutral-500">Daily Intelligence Monitor</p>
          <h1 className="mt-1 text-2xl font-semibold text-neutral-950">AIRS 情报卡片监测台</h1>
          <p className="mt-1 text-sm text-neutral-600">
            统一查看市场情报与社媒信号，优先处理未进入简报的卡片。
          </p>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-xs text-neutral-500">
            最近运行：{formatShortDateTime(stats.latest_run_at)}
          </p>
          <button
            type="button"
            onClick={loadData}
            className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-800 hover:border-neutral-400 hover:bg-neutral-50"
          >
            刷新
          </button>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <KpiCard label="市场情报" value={stats.market_cards} tone="blue" />
        <KpiCard label="社媒信号" value={stats.social_cards} tone="rose" />
        <KpiCard label="待简报" value={stats.unbriefed_cards} tone="amber" />
        <KpiCard label="高影响" value={stats.high_impact_cards} tone="violet" />
        <KpiCard label="原始来源" value={stats.raw_sources} tone="emerald" />
        <KpiCard label="最近运行" value={stats.total_runs} tone="neutral" />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(360px,1fr)]">
        <div className="rounded-lg border border-neutral-200 bg-white">
          <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold text-neutral-950">优先卡片流</h2>
              <p className="text-xs text-neutral-500">按最近出现时间排序，优先看未简报和高影响卡片。</p>
            </div>
            <Link href="/cards" className="text-sm font-medium text-blue-700 hover:text-blue-900">
              查看全部
            </Link>
          </div>
          {cards.length === 0 ? (
            <div className="p-8 text-center text-sm text-neutral-500">暂无情报卡片</div>
          ) : (
            <div className="divide-y divide-neutral-100">
              {cards.map((doc) => (
                <PriorityCard key={doc.id} doc={doc} />
              ))}
            </div>
          )}
        </div>

        <div className="space-y-5">
          <DistributionPanel
            title="地区分布"
            data={stats.by_region}
            labels={REGION_LABELS}
          />
          <DistributionPanel
            title="业务影响标签"
            data={stats.by_impact_tag}
            labels={IMPACT_TAG_LABELS}
            limit={6}
          />
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <DistributionPanel title="主题分布" data={stats.by_topic} labels={TOPIC_LABELS} />
        <RecentRuns runs={stats.recent_runs} />
      </section>
    </div>
  );
}

function KpiCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "blue" | "rose" | "amber" | "violet" | "emerald" | "neutral";
}) {
  const tones = {
    blue: "border-blue-200 bg-blue-50 text-blue-800",
    rose: "border-rose-200 bg-rose-50 text-rose-800",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    violet: "border-violet-200 bg-violet-50 text-violet-800",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-800",
    neutral: "border-neutral-200 bg-white text-neutral-900",
  };

  return (
    <div className={`rounded-lg border p-4 ${tones[tone]}`}>
      <p className="text-xs font-medium opacity-75">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function PriorityCard({ doc }: { doc: Document }) {
  const meta = doc.metadata || {};
  const isSocial = doc.doc_type === "social_signal_card";
  const tags = meta.impact_tags ?? [];
  const status = getBriefingStatus(doc);
  const score = meta.importance_score ?? meta.relevance_score ?? meta.confidence_score;

  return (
    <Link href={`/cards/${doc.id}`} className="block px-4 py-3 hover:bg-neutral-50">
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone={isSocial ? "rose" : "blue"}>{labelFor(DOC_TYPE_LABELS, doc.doc_type)}</Chip>
        <Chip tone="neutral">
          {isSocial
            ? labelFor(SIGNAL_TYPE_LABELS, meta.signal_type)
            : labelFor(TOPIC_LABELS, meta.topic)}
        </Chip>
        <Chip tone={status === "briefed" ? "emerald" : "amber"}>
          {labelFor(BRIEFING_STATUS_LABELS, status)}
        </Chip>
        <span className="ml-auto text-xs text-neutral-500">
          最近出现：{formatShortDateTime(getCardLastSeenAt(doc))}
        </span>
      </div>
      <div className="mt-2 grid gap-2 lg:grid-cols-[minmax(0,1fr)_220px]">
        <div>
          <h3 className="line-clamp-1 text-sm font-semibold text-neutral-950">{doc.title}</h3>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-600">{doc.content}</p>
        </div>
        <div className="text-xs text-neutral-500 lg:text-right">
          <p>{isSocial ? formatList(meta.platforms) : labelFor(REGION_LABELS, meta.region)}</p>
          <p>发布时间：{formatShortDateTime(getCardPublishedAt(doc))}</p>
          <p>分数：{formatScore(score)}</p>
        </div>
      </div>
      {tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {tags.slice(0, 5).map((tag) => (
            <Chip key={tag} tone="slate">
              {labelFor(IMPACT_TAG_LABELS, tag)}
            </Chip>
          ))}
        </div>
      )}
    </Link>
  );
}

function DistributionPanel({
  title,
  data,
  labels,
  limit = 8,
}: {
  title: string;
  data: Record<string, number>;
  labels: Record<string, string>;
  limit?: number;
}) {
  const rows = Object.entries(data)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
  const max = Math.max(...rows.map(([, count]) => count), 1);

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-neutral-950">{title}</h2>
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-neutral-500">暂无数据</p>
      ) : (
        <div className="mt-4 space-y-3">
          {rows.map(([key, count]) => (
            <div key={key}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-neutral-600">{labelFor(labels, key)}</span>
                <span className="font-medium text-neutral-900">{count}</span>
              </div>
              <div className="h-2 rounded-full bg-neutral-100">
                <div
                  className="h-2 rounded-full bg-neutral-800"
                  style={{ width: `${(count / max) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RecentRuns({ runs }: { runs: Stats["recent_runs"] }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-neutral-950">最近 Agent 运行</h2>
      {runs.length === 0 ? (
        <p className="mt-4 text-sm text-neutral-500">暂无运行记录</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-neutral-500">
              <tr className="border-b border-neutral-200">
                <th className="py-2 font-medium">Agent</th>
                <th className="py-2 font-medium">状态</th>
                <th className="py-2 font-medium">时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100 text-neutral-700">
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="py-2">{labelFor(AGENT_LABELS, run.agent_name)}</td>
                  <td className="py-2">{run.status}</td>
                  <td className="py-2">{formatShortDateTime(run.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Chip({
  tone,
  children,
}: {
  tone: "blue" | "rose" | "amber" | "emerald" | "neutral" | "slate";
  children: React.ReactNode;
}) {
  const tones = {
    blue: "border-blue-200 bg-blue-50 text-blue-700",
    rose: "border-rose-200 bg-rose-50 text-rose-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
    neutral: "border-neutral-200 bg-neutral-50 text-neutral-700",
    slate: "border-slate-200 bg-slate-50 text-slate-600",
  };

  return (
    <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

function formatList(values?: string[]) {
  if (!values || values.length === 0) return "未标注";
  return values.join(" / ");
}

function DashboardSkeleton() {
  return (
    <div className="space-y-5 animate-pulse">
      <div className="h-20 rounded-lg bg-neutral-200" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        {[1, 2, 3, 4, 5, 6].map((item) => (
          <div key={item} className="h-24 rounded-lg bg-neutral-200" />
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(360px,1fr)]">
        <div className="h-96 rounded-lg bg-neutral-200" />
        <div className="space-y-5">
          <div className="h-44 rounded-lg bg-neutral-200" />
          <div className="h-44 rounded-lg bg-neutral-200" />
        </div>
      </div>
    </div>
  );
}
