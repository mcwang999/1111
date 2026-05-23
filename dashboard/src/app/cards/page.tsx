"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Document, ApiResponse } from "@/lib/types";
import {
  REGION_LABELS,
  TOPIC_LABELS,
  IMPACT_TAG_LABELS,
  VERTICAL_LABELS,
  AGENT_LABELS,
} from "@/lib/types";

const ALL_REGIONS = Object.keys(REGION_LABELS);
const ALL_TOPICS = Object.keys(TOPIC_LABELS);
const ALL_TAGS = Object.keys(IMPACT_TAG_LABELS);
const ALL_VERTICALS = Object.keys(VERTICAL_LABELS);
const ALL_AGENTS = Object.keys(AGENT_LABELS);

export default function CardsPage() {
  return (
    <Suspense fallback={<CardsSkeleton />}>
      <CardsContent />
    </Suspense>
  );
}

function CardsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [data, setData] = useState<ApiResponse<Document> | null>(null);
  const [loading, setLoading] = useState(true);

  // Read filters from URL
  const region = searchParams.get("region") || "";
  const topic = searchParams.get("topic") || "";
  const tags = searchParams.get("impact_tags") || "";
  const vertical = searchParams.get("strategic_vertical") || "";
  const agent = searchParams.get("created_by_agent") || "";
  const page = parseInt(searchParams.get("page") || "1", 10);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ doc_type: "intel_card", limit: "20" });
    if (region) params.set("region", region);
    if (topic) params.set("topic", topic);
    if (tags) params.set("impact_tags", tags);
    if (vertical) params.set("strategic_vertical", vertical);
    if (agent) params.set("created_by_agent", agent);
    params.set("page", String(page));

    try {
      const res = await fetch(`/api/documents?${params}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [region, topic, tags, vertical, agent, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const setFilter = (key: string, value: string) => {
    const p = new URLSearchParams(searchParams.toString());
    if (value) p.set(key, value);
    else p.delete(key);
    p.set("page", "1"); // reset to page 1 on filter change
    router.push(`/cards?${p.toString()}`);
  };

  const totalPages = data ? Math.ceil(data.count / data.limit) : 0;

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-slate-900">情报卡片</h1>

      {/* Filter bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="flex flex-wrap gap-3 items-end">
          <FilterSelect
            label="区域"
            value={region}
            onChange={(v) => setFilter("region", v)}
            options={ALL_REGIONS}
            optionLabels={REGION_LABELS}
            placeholder="全部区域"
          />
          <FilterSelect
            label="主题"
            value={topic}
            onChange={(v) => setFilter("topic", v)}
            options={ALL_TOPICS}
            optionLabels={TOPIC_LABELS}
            placeholder="全部主题"
          />
          <FilterSelect
            label="影响标签"
            value={tags}
            onChange={(v) => setFilter("impact_tags", v)}
            options={ALL_TAGS}
            optionLabels={IMPACT_TAG_LABELS}
            placeholder="全部标签"
          />
          <FilterSelect
            label="垂直领域"
            value={vertical}
            onChange={(v) => setFilter("strategic_vertical", v)}
            options={ALL_VERTICALS}
            optionLabels={VERTICAL_LABELS}
            placeholder="全部"
          />
          <FilterSelect
            label="采集 Agent"
            value={agent}
            onChange={(v) => setFilter("created_by_agent", v)}
            options={ALL_AGENTS}
            optionLabels={AGENT_LABELS}
            placeholder="全部 Agent"
          />
        </div>
      </div>

      {/* Results */}
      {loading ? (
        <CardsSkeleton />
      ) : !data || data.data.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-400">
          暂无情报卡片
        </div>
      ) : (
        <>
          <p className="text-sm text-slate-500">
            共 {data.count} 条结果，第 {data.page}/{Math.max(1, totalPages)} 页
          </p>
          <div className="space-y-3">
            {data.data.map((doc) => (
              <CardItem key={doc.id} doc={doc} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center gap-2 pt-2">
              <PageBtn
                disabled={page <= 1}
                onClick={() => setFilter("page", String(page - 1))}
              >
                ← 上一页
              </PageBtn>
              <span className="px-3 py-1.5 text-sm text-slate-500">
                {page} / {totalPages}
              </span>
              <PageBtn
                disabled={page >= totalPages}
                onClick={() => setFilter("page", String(page + 1))}
              >
                下一页 →
              </PageBtn>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ---------- Sub-components ---------- */

function FilterSelect({
  label,
  value,
  onChange,
  options,
  optionLabels,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  optionLabels: Record<string, string>;
  placeholder: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-slate-500">{label}</label>
      <select
        className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white min-w-[140px] focus:outline-none focus:ring-2 focus:ring-sky-400"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{placeholder}</option>
        {options.map((k) => (
          <option key={k} value={k}>
            {optionLabels[k] || k}
          </option>
        ))}
      </select>
    </div>
  );
}

function CardItem({ doc }: { doc: Document }) {
  const meta = doc.metadata || {};
  const tags = meta.impact_tags || [];

  return (
    <a
      href={`/cards/${doc.id}`}
      className="block bg-white rounded-xl border border-slate-200 p-4 hover:border-sky-300 hover:shadow-sm transition-all"
    >
      <div className="flex items-start gap-2 mb-1">
        <span className="text-xs px-2 py-0.5 rounded-full bg-sky-50 text-sky-600 font-medium shrink-0">
          {REGION_LABELS[meta.region || ""] || meta.region || "未知"}
        </span>
        <span className="text-xs px-2 py-0.5 rounded-full bg-violet-50 text-violet-600 font-medium shrink-0">
          {TOPIC_LABELS[meta.topic || ""] || meta.topic || "未知"}
        </span>
        <span className="text-xs text-slate-400 ml-auto shrink-0">
          {AGENT_LABELS[doc.created_by_agent] || doc.created_by_agent}
        </span>
        <span className="text-xs text-slate-400 shrink-0">
          {formatTime(doc.created_at)}
        </span>
      </div>
      <h3 className="text-sm font-semibold text-slate-800 mb-1 line-clamp-2">
        {doc.title}
      </h3>
      <p className="text-xs text-slate-500 line-clamp-2 mb-2">{doc.content}</p>
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {tags.map((t: string) => (
            <span
              key={t}
              className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500"
            >
              {IMPACT_TAG_LABELS[t] || t}
            </span>
          ))}
        </div>
      )}
    </a>
  );
}

function PageBtn({
  disabled,
  onClick,
  children,
}: {
  disabled: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
        disabled
          ? "border-slate-200 text-slate-300 cursor-not-allowed"
          : "border-slate-300 text-slate-600 hover:bg-slate-100"
      }`}
    >
      {children}
    </button>
  );
}

function CardsSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="bg-white rounded-xl border border-slate-200 p-4">
          <div className="flex gap-2 mb-2">
            <div className="h-5 w-16 bg-slate-200 rounded-full" />
            <div className="h-5 w-16 bg-slate-200 rounded-full" />
          </div>
          <div className="h-4 w-3/4 bg-slate-200 rounded mb-2" />
          <div className="h-3 w-full bg-slate-200 rounded mb-1" />
          <div className="h-3 w-1/2 bg-slate-200 rounded" />
        </div>
      ))}
    </div>
  );
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
