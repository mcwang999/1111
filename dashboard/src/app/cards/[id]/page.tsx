"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Document } from "@/lib/types";
import {
  AGENT_LABELS,
  BRIEFING_STATUS_LABELS,
  DOC_TYPE_LABELS,
  IMPACT_TAG_LABELS,
  REGION_LABELS,
  SENTIMENT_LABELS,
  SIGNAL_TYPE_LABELS,
  TOPIC_LABELS,
  VERTICAL_LABELS,
  formatDateTime,
  formatScore,
  getBriefingStatus,
  getCardLastSeenAt,
  getCardPublishedAt,
  labelFor,
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
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError("");
      fetch(`/api/documents/${id}`)
        .then((res) => {
          if (!res.ok) throw new Error("未找到这张情报卡片");
          return res.json();
        })
        .then(setData)
        .catch((err) => setError(err instanceof Error ? err.message : "加载失败"))
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [id]);

  if (loading) return <DetailSkeleton />;
  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }
  if (!data) {
    return <div className="text-sm text-neutral-500">未找到情报卡片</div>;
  }

  const doc = data.document;
  const meta = doc.metadata || {};
  const isSocial = doc.doc_type === "social_signal_card";
  const status = getBriefingStatus(doc);
  const sourceUrl = doc.source_url || meta.source_url || meta.url;
  const score = meta.importance_score ?? meta.relevance_score ?? meta.confidence_score;

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <Link href="/cards" className="text-sm font-medium text-blue-700 hover:text-blue-900">
        返回情报卡片流
      </Link>

      <section className="rounded-lg border border-neutral-200 bg-white">
        <div className="border-b border-neutral-200 px-5 py-4">
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
            {sourceUrl && (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-auto text-sm font-medium text-blue-700 hover:text-blue-900"
              >
                查看原文
              </a>
            )}
          </div>
          <h1 className="mt-3 text-2xl font-semibold leading-tight text-neutral-950">{doc.title}</h1>
        </div>

        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <article className="whitespace-pre-wrap text-sm leading-7 text-neutral-700">{doc.content}</article>

          <aside className="space-y-4">
            <div className="rounded-lg border border-neutral-200 p-4">
              <h2 className="text-sm font-semibold text-neutral-950">运营元数据</h2>
              <div className="mt-3 space-y-2 text-xs">
                <MetaLine label="发布时间" value={formatDateTime(getCardPublishedAt(doc))} />
                <MetaLine label="首次发现" value={formatDateTime(meta.first_seen_at)} />
                <MetaLine label="最近出现" value={formatDateTime(getCardLastSeenAt(doc))} />
                <MetaLine label="已简报时间" value={formatDateTime(meta.briefed_at)} />
                <MetaLine label="Agent" value={labelFor(AGENT_LABELS, doc.created_by_agent)} />
                <MetaLine label="去重 Key" value={meta.dedup_key || meta.event_key || "-"} />
                <MetaLine label="分数" value={formatScore(score)} />
              </div>
            </div>

            <div className="rounded-lg border border-neutral-200 p-4">
              <h2 className="text-sm font-semibold text-neutral-950">业务标签</h2>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {(meta.impact_tags ?? []).length > 0 ? (
                  meta.impact_tags!.map((tag) => (
                    <Chip key={tag} tone="slate">
                      {labelFor(IMPACT_TAG_LABELS, tag)}
                    </Chip>
                  ))
                ) : (
                  <span className="text-xs text-neutral-500">暂无标签</span>
                )}
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-lg border border-neutral-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-neutral-950">卡片属性</h2>
          <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
            <MetaLine label="地区" value={isSocial ? formatRegions(meta.regions) : labelFor(REGION_LABELS, meta.region)} />
            <MetaLine label="主题" value={labelFor(TOPIC_LABELS, meta.topic)} />
            <MetaLine label="垂直领域" value={labelFor(VERTICAL_LABELS, meta.strategic_vertical)} />
            <MetaLine label="信号类型" value={labelFor(SIGNAL_TYPE_LABELS, meta.signal_type)} />
            <MetaLine label="平台" value={formatList(meta.platforms)} />
            <MetaLine label="情绪" value={labelFor(SENTIMENT_LABELS, meta.sentiment)} />
            <MetaLine label="来源数" value={String(meta.source_count ?? "-")} />
            <MetaLine label="帖子数" value={String(meta.post_count ?? "-")} />
          </div>
        </div>

        <div className="rounded-lg border border-neutral-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-neutral-950">评分</h2>
          <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
            <MetaLine label="重要度" value={formatScore(meta.importance_score)} />
            <MetaLine label="相关度" value={formatScore(meta.relevance_score)} />
            <MetaLine label="置信度" value={formatScore(meta.confidence_score)} />
            <MetaLine label="LLM 相关度" value={formatScore(meta.llm_relevance_score)} />
          </div>
          {meta.llm_keep_reason && (
            <p className="mt-4 text-xs leading-5 text-neutral-600">{meta.llm_keep_reason}</p>
          )}
        </div>
      </section>

      {data.linked_sources.length > 0 && (
        <section className="rounded-lg border border-neutral-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-neutral-950">
            关联原始来源 ({data.linked_sources.length})
          </h2>
          <div className="mt-4 space-y-3">
            {data.linked_sources.map((source) => (
              <SourceItem key={source.id} source={source} />
            ))}
          </div>
        </section>
      )}

      <section className="rounded-lg border border-neutral-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-neutral-950">Raw Metadata</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <tbody className="divide-y divide-neutral-100">
              {Object.entries(meta)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([key, value]) => (
                  <tr key={key}>
                    <th className="w-56 py-2 pr-4 font-medium text-neutral-500">{key}</th>
                    <td className="py-2 text-neutral-800">{renderValue(value)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function SourceItem({ source }: { source: Document }) {
  const meta = source.metadata || {};
  const sourceUrl = source.source_url || meta.source_url || meta.url;

  return (
    <div className="rounded-lg border border-neutral-200 p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
        <Chip tone="neutral">原始来源</Chip>
        <span>{meta.source_name || "未知来源"}</span>
        <span className="ml-auto">{formatDateTime(meta.published_at || source.created_at)}</span>
      </div>
      <h3 className="line-clamp-1 text-sm font-medium text-neutral-900">{source.title}</h3>
      <p className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-600">{source.content}</p>
      {sourceUrl && (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-xs font-medium text-blue-700 hover:text-blue-900"
        >
          查看来源
        </a>
      )}
    </div>
  );
}

function MetaLine({ label, value }: { label: string; value: string }) {
  return (
    <p className="flex gap-2">
      <span className="shrink-0 text-neutral-400">{label}：</span>
      <span className="min-w-0 break-words text-neutral-800">{value}</span>
    </p>
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

function formatRegions(values?: string[]) {
  if (!values || values.length === 0) return "未标注";
  return values.map((value) => labelFor(REGION_LABELS, value)).join(" / ");
}

function renderValue(value: unknown) {
  if (value === null || typeof value === "undefined") return "-";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value, null, 2);
}

function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-5xl space-y-5 animate-pulse">
      <div className="h-5 w-32 rounded bg-neutral-200" />
      <div className="h-80 rounded-lg bg-neutral-200" />
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="h-40 rounded-lg bg-neutral-200" />
        <div className="h-40 rounded-lg bg-neutral-200" />
      </div>
    </div>
  );
}
