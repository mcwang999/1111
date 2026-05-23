"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import type { Document } from "@/lib/types";
import {
  REGION_LABELS,
  TOPIC_LABELS,
  IMPACT_TAG_LABELS,
  VERTICAL_LABELS,
  AGENT_LABELS,
} from "@/lib/types";

interface DetailData {
  document: Document;
  linked_sources: Document[];
}

export default function CardDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<DetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    fetch(`/api/documents/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("Not found");
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <DetailSkeleton />;
  if (error) return <div className="text-red-500">加载失败: {error}</div>;
  if (!data) return <div className="text-slate-400">未找到</div>;

  const doc = data.document;
  const meta = doc.metadata || {};

  return (
    <div className="space-y-6 max-w-4xl">
      <a href="/cards" className="text-sm text-sky-600 hover:underline">
        ← 返回情报列表
      </a>

      {/* Card header */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <Badge color="sky">{REGION_LABELS[meta.region || ""] || meta.region || "未知区域"}</Badge>
          <Badge color="violet">{TOPIC_LABELS[meta.topic || ""] || meta.topic || "未知主题"}</Badge>
          <Badge color="emerald">
            {VERTICAL_LABELS[meta.strategic_vertical || ""] || meta.strategic_vertical || "未知"}
          </Badge>
          {meta.source_url && (
            <a
              href={meta.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-sky-600 hover:underline ml-auto"
            >
              查看原文 ↗
            </a>
          )}
        </div>

        <h1 className="text-xl font-bold text-slate-900 mb-3">{doc.title}</h1>

        <div className="prose prose-sm max-w-none text-slate-600 mb-4 whitespace-pre-wrap">
          {doc.content}
        </div>

        {/* Metadata grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm border-t border-slate-100 pt-4">
          <MetaItem label="Agent" value={AGENT_LABELS[doc.created_by_agent] || doc.created_by_agent} />
          <MetaItem label="Event Key" value={meta.event_key || "-"} />
          <MetaItem label="关联源数量" value={String(meta.source_count || 0)} />
          <MetaItem label="重复检测" value={meta.dedup_method || "-"} />
          <MetaItem label="相关性评分" value={meta.relevance_score?.toFixed(2) ?? "-"} />
          <MetaItem label="置信度评分" value={meta.confidence_score?.toFixed(2) ?? "-"} />
          <MetaItem label="重要度评分" value={meta.importance_score?.toFixed(2) ?? "-"} />
          <MetaItem label="采集时间" value={formatTime(doc.created_at)} />
        </div>

        {/* Impact tags */}
        {(meta.impact_tags ?? []).length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <p className="text-xs font-medium text-slate-500 mb-2">影响标签</p>
            <div className="flex flex-wrap gap-1.5">
              {meta.impact_tags!.map((t: string) => (
                <span
                  key={t}
                  className="text-xs px-2 py-1 rounded-md bg-amber-50 text-amber-700 border border-amber-200"
                >
                  {IMPACT_TAG_LABELS[t] || t}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* LLM reason */}
        {meta.llm_keep_reason && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <p className="text-xs font-medium text-slate-500 mb-1">LLM 保留原因</p>
            <p className="text-sm text-slate-600">{meta.llm_keep_reason}</p>
          </div>
        )}
      </div>

      {/* Linked raw sources (traceability) */}
      {data.linked_sources.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-base font-semibold text-slate-800 mb-4">
            数据溯源 ({data.linked_sources.length})
          </h2>
          <div className="space-y-3">
            {data.linked_sources.map((src) => {
              const srcMeta = src.metadata || {};
              return (
                <div
                  key={src.id}
                  className="border border-slate-200 rounded-lg p-3 hover:border-sky-200 transition-colors"
                >
                  <div className="flex items-start gap-2 mb-1">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-sky-50 text-sky-600 font-medium">
                      原始数据
                    </span>
                    <span className="text-xs text-slate-400">
                      {srcMeta.source_name || "未知来源"}
                    </span>
                    {srcMeta.published_at && (
                      <span className="text-xs text-slate-400 ml-auto">
                        {srcMeta.published_at}
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-medium text-slate-700 mb-1">
                    {src.title}
                  </h3>
                  <p className="text-xs text-slate-500 line-clamp-2 mb-1">
                    {src.content}
                  </p>
                  <a
                    href={src.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-sky-600 hover:underline"
                  >
                    查看原文 ↗
                  </a>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* No linked sources */}
      {data.linked_sources.length === 0 && doc.doc_type === "intel_card" && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 text-center text-sm text-slate-400">
          暂无可溯源的原始数据
        </div>
      )}
    </div>
  );
}

/* ---------- Sub-components ---------- */

function Badge({
  color,
  children,
}: {
  color: "sky" | "violet" | "emerald";
  children: React.ReactNode;
}) {
  const colors = {
    sky: "bg-sky-50 text-sky-600",
    violet: "bg-violet-50 text-violet-600",
    emerald: "bg-emerald-50 text-emerald-600",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[color]}`}>
      {children}
    </span>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-sm font-medium text-slate-700">{value}</p>
    </div>
  );
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function DetailSkeleton() {
  return (
    <div className="space-y-6 animate-pulse max-w-4xl">
      <div className="h-4 w-24 bg-slate-200 rounded" />
      <div className="bg-white rounded-xl border p-6">
        <div className="flex gap-2 mb-3">
          <div className="h-5 w-16 bg-slate-200 rounded-full" />
          <div className="h-5 w-16 bg-slate-200 rounded-full" />
        </div>
        <div className="h-6 w-3/4 bg-slate-200 rounded mb-3" />
        <div className="h-4 w-full bg-slate-200 rounded mb-2" />
        <div className="h-4 w-full bg-slate-200 rounded mb-2" />
        <div className="h-4 w-1/2 bg-slate-200 rounded" />
      </div>
    </div>
  );
}
