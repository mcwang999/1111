"use client";

import { useEffect, useState } from "react";
import type { Stats } from "@/lib/types";
import { REGION_LABELS, TOPIC_LABELS, AGENT_LABELS } from "@/lib/types";

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/stats")
      .then((r) => r.json())
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSkeleton />;
  if (!stats) return <div className="text-red-500">加载失败</div>;

  const regionKeys = Object.keys(stats.by_region).sort();
  const topicKeys = Object.keys(stats.by_topic).sort();
  const regionColors = ["#0ea5e9", "#8b5cf6", "#22c55e", "#f59e0b", "#ef4444"];
  const topicColors = ["#0ea5e9", "#8b5cf6", "#22c55e", "#f59e0b", "#ef4444"];

  const maxRegion = Math.max(...regionKeys.map((k) => stats.by_region[k]), 1);
  const maxTopic = Math.max(...topicKeys.map((k) => stats.by_topic[k]), 1);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">概览</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard label="情报卡片" value={stats.total_cards} color="sky" />
        <StatCard label="原始数据" value={stats.total_sources} color="violet" />
        <StatCard label="采集记录" value={stats.total_runs} color="emerald" />
      </div>

      {/* Region breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">按区域分布</h2>
          {regionKeys.length === 0 ? (
            <p className="text-sm text-slate-400">暂无数据</p>
          ) : (
            <div className="space-y-3">
              {regionKeys.map((key, i) => {
                const count = stats.by_region[key];
                const pct = (count / maxRegion) * 100;
                return (
                  <div key={key}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-slate-600">{REGION_LABELS[key] || key}</span>
                      <span className="font-medium text-slate-800">{count}</span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: regionColors[i % regionColors.length],
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Topic breakdown */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">按情报主题分布</h2>
          {topicKeys.length === 0 ? (
            <p className="text-sm text-slate-400">暂无数据</p>
          ) : (
            <div className="space-y-3">
              {topicKeys.map((key, i) => {
                const count = stats.by_topic[key];
                const pct = (count / maxTopic) * 100;
                return (
                  <div key={key}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-slate-600">{TOPIC_LABELS[key] || key}</span>
                      <span className="font-medium text-slate-800">{count}</span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: topicColors[i % topicColors.length],
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Recent agent runs */}
      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <h2 className="text-sm font-semibold text-slate-700 mb-4">最近采集记录</h2>
        {stats.recent_runs.length === 0 ? (
          <p className="text-sm text-slate-400">暂无记录</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="pb-2 pr-4 font-medium">Agent</th>
                  <th className="pb-2 pr-4 font-medium">状态</th>
                  <th className="pb-2 pr-4 font-medium">情报卡</th>
                  <th className="pb-2 pr-4 font-medium">原始源</th>
                  <th className="pb-2 font-medium">时间</th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_runs.map((run) => {
                  const out = run.output_payload as Record<string, number>;
                  return (
                    <tr key={run.id} className="border-b border-slate-100 text-slate-700">
                      <td className="py-2.5 pr-4">
                        {AGENT_LABELS[run.agent_name] || run.agent_name}
                      </td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge status={run.status} />
                      </td>
                      <td className="py-2.5 pr-4">{out?.intel_card_count ?? "-"}</td>
                      <td className="py-2.5 pr-4">{out?.raw_source_count ?? "-"}</td>
                      <td className="py-2.5 text-slate-400 text-xs whitespace-nowrap">
                        {formatTime(run.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- Sub-components ---------- */

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: "sky" | "violet" | "emerald";
}) {
  const colors = {
    sky: "bg-sky-50 border-sky-200 text-sky-600",
    violet: "bg-violet-50 border-violet-200 text-violet-600",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-600",
  };
  return (
    <div className={`rounded-xl border p-5 ${colors[color]}`}>
      <p className="text-sm opacity-80">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-emerald-100 text-emerald-700",
    empty: "bg-amber-100 text-amber-700",
    partial: "bg-rose-100 text-rose-700",
  };
  const labels: Record<string, string> = {
    completed: "完成",
    empty: "无数据",
    partial: "部分失败",
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
        colors[status] || "bg-slate-100 text-slate-600"
      }`}
    >
      {labels[status] || status}
    </span>
  );
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-24 bg-slate-200 rounded" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 bg-slate-200 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-64 bg-slate-200 rounded-xl" />
        <div className="h-64 bg-slate-200 rounded-xl" />
      </div>
    </div>
  );
}
