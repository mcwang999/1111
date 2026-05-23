"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Document, ApiResponse } from "@/lib/types";
import { REGION_LABELS, AGENT_LABELS } from "@/lib/types";

const ALL_AGENTS = Object.keys(AGENT_LABELS);

export default function SourcesPage() {
  return (
    <Suspense fallback={<SourcesSkeleton />}>
      <SourcesContent />
    </Suspense>
  );
}

function SourcesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [data, setData] = useState<ApiResponse<Document> | null>(null);
  const [loading, setLoading] = useState(true);

  const agent = searchParams.get("created_by_agent") || "";
  const page = parseInt(searchParams.get("page") || "1", 10);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({
      doc_type: "raw_source",
      limit: "30",
      sort: "created_at",
      dir: "desc",
    });
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
  }, [agent, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const setFilter = (key: string, value: string) => {
    const p = new URLSearchParams(searchParams.toString());
    if (value) p.set(key, value);
    else p.delete(key);
    p.set("page", "1");
    router.push(`/sources?${p.toString()}`);
  };

  const totalPages = data ? Math.ceil(data.count / data.limit) : 0;

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-slate-900">数据溯源</h1>
      <p className="text-sm text-slate-500">
        浏览所有原始采集数据，与情报卡片关联实现溯源
      </p>

      {/* Filter */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="flex flex-wrap gap-3 items-end">
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

      {loading ? (
        <SourcesSkeleton />
      ) : !data || data.data.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-400">
          暂无原始数据
        </div>
      ) : (
        <>
          <p className="text-sm text-slate-500">
            共 {data.count} 条结果
          </p>
          <div className="space-y-2">
            {data.data.map((doc) => {
              const meta = doc.metadata || {};
              return (
                <div
                  key={doc.id}
                  className="bg-white rounded-lg border border-slate-200 p-3 hover:border-sky-200 transition-colors"
                >
                  <div className="flex items-start gap-2 mb-1">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-sky-50 text-sky-600 font-medium shrink-0">
                      {REGION_LABELS[meta.region || ""] || meta.region || "未知"}
                    </span>
                    <span className="text-xs text-slate-400">
                      {meta.source_name || "未知来源"}
                    </span>
                    {meta.published_at && (
                      <span className="text-xs text-slate-400 ml-auto">
                        {meta.published_at}
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-medium text-slate-700 mb-0.5 line-clamp-1">
                    {doc.title}
                  </h3>
                  <p className="text-xs text-slate-500 line-clamp-2 mb-1">
                    {doc.content}
                  </p>
                  <a
                    href={doc.source_url}
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

          {totalPages > 1 && (
            <div className="flex justify-center gap-2 pt-2">
              <button
                disabled={page <= 1}
                onClick={() => setFilter("page", String(page - 1))}
                className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  page <= 1
                    ? "border-slate-200 text-slate-300 cursor-not-allowed"
                    : "border-slate-300 text-slate-600 hover:bg-slate-100"
                }`}
              >
                ← 上一页
              </button>
              <span className="px-3 py-1.5 text-sm text-slate-500">
                {page} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setFilter("page", String(page + 1))}
                className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                  page >= totalPages
                    ? "border-slate-200 text-slate-300 cursor-not-allowed"
                    : "border-slate-300 text-slate-600 hover:bg-slate-100"
                }`}
              >
                下一页 →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

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
        className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white min-w-[160px] focus:outline-none focus:ring-2 focus:ring-sky-400"
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

function SourcesSkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="bg-white rounded-lg border border-slate-200 p-3">
          <div className="h-4 w-1/3 bg-slate-200 rounded mb-2" />
          <div className="h-3 w-full bg-slate-200 rounded mb-1" />
          <div className="h-3 w-2/3 bg-slate-200 rounded" />
        </div>
      ))}
    </div>
  );
}
