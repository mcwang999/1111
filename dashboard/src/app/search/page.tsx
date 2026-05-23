"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Document, ApiResponse } from "@/lib/types";
import {
  REGION_LABELS,
  TOPIC_LABELS,
  IMPACT_TAG_LABELS,
  AGENT_LABELS,
} from "@/lib/types";

export default function SearchPage() {
  return (
    <Suspense fallback={<SearchSkeleton />}>
      <SearchContent />
    </Suspense>
  );
}

function SearchContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const q = searchParams.get("q") || "";
  const docType = searchParams.get("doc_type") || "";
  const page = parseInt(searchParams.get("page") || "1", 10);

  const [data, setData] = useState<ApiResponse<Document> | null>(null);
  const [input, setInput] = useState(q);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!q) {
      setData(null);
      return;
    }

    setLoading(true);
    const params = new URLSearchParams({ q, limit: "20" });
    if (docType) params.set("doc_type", docType);
    params.set("page", String(page));

    fetch(`/api/search?${params}`)
      .then((r) => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [q, docType, page]);

  const doSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams();
    if (input.trim()) params.set("q", input.trim());
    if (docType) params.set("doc_type", docType);
    router.push(`/search?${params.toString()}`);
  };

  const totalPages = data ? Math.ceil(data.count / data.limit) : 0;

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-slate-900">搜索</h1>

      {/* Search form */}
      <form onSubmit={doSearch} className="flex gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="搜索情报卡片和原始数据..."
          className="flex-1 border border-slate-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-sky-400"
        />
        <select
          value={docType}
          onChange={(e) => {
            const params = new URLSearchParams(searchParams.toString());
            if (e.target.value) params.set("doc_type", e.target.value);
            else params.delete("doc_type");
            if (q) params.set("q", q);
            router.push(`/search?${params.toString()}`);
          }}
          className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-sky-400"
        >
          <option value="">全部类型</option>
          <option value="intel_card">情报卡片</option>
          <option value="raw_source">原始数据</option>
          <option value="social_signal_card">社交信号</option>
        </select>
        <button
          type="submit"
          className="px-5 py-2.5 bg-sky-500 text-white text-sm font-medium rounded-lg hover:bg-sky-600 transition-colors"
        >
          搜索
        </button>
      </form>

      {/* Results */}
      {loading ? (
        <SearchSkeleton />
      ) : !q ? (
        <div className="text-center text-slate-400 py-20">
          输入关键词搜索情报内容
        </div>
      ) : !data || data.data.length === 0 ? (
        <div className="text-center text-slate-400 py-20">
          未找到与「{q}」相关的结果
        </div>
      ) : (
        <>
          <p className="text-sm text-slate-500">
            搜索「{q}」共 {data.count} 条结果
          </p>
          <div className="space-y-3">
            {data.data.map((doc) => {
              const meta = doc.metadata || {};
              const tags = meta.impact_tags || [];

              return (
                <a
                  key={doc.id}
                  href={`/cards/${doc.id}`}
                  className="block bg-white rounded-xl border border-slate-200 p-4 hover:border-sky-300 hover:shadow-sm transition-all"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <DocTypeBadge type={doc.doc_type} />
                    {meta.region && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-sky-50 text-sky-600 font-medium">
                        {REGION_LABELS[meta.region] || meta.region}
                      </span>
                    )}
                    {meta.topic && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-violet-50 text-violet-600 font-medium">
                        {TOPIC_LABELS[meta.topic] || meta.topic}
                      </span>
                    )}
                    <span className="text-xs text-slate-400 ml-auto">
                      {AGENT_LABELS[doc.created_by_agent] || doc.created_by_agent}
                    </span>
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800 mb-1 line-clamp-2">
                    {highlightMatch(doc.title, q)}
                  </h3>
                  <p className="text-xs text-slate-500 line-clamp-2 mb-2">
                    {highlightMatch(doc.content, q)}
                  </p>
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
            })}
          </div>

          {totalPages > 1 && (
            <div className="flex justify-center gap-2 pt-2">
              <button
                disabled={page <= 1}
                onClick={() => {
                  const p = new URLSearchParams(searchParams.toString());
                  p.set("page", String(page - 1));
                  router.push(`/search?${p.toString()}`);
                }}
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
                onClick={() => {
                  const p = new URLSearchParams(searchParams.toString());
                  p.set("page", String(page + 1));
                  router.push(`/search?${p.toString()}`);
                }}
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

/* ---------- Sub-components ---------- */

function DocTypeBadge({ type }: { type: string }) {
  const map: Record<string, { label: string; color: string }> = {
    intel_card: { label: "情报卡", color: "bg-sky-100 text-sky-700" },
    raw_source: { label: "原始数据", color: "bg-amber-100 text-amber-700" },
    social_signal_card: { label: "社交信号", color: "bg-rose-100 text-rose-700" },
  };
  const info = map[type] || { label: type, color: "bg-slate-100 text-slate-600" };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${info.color}`}>
      {info.label}
    </span>
  );
}

function highlightMatch(text: string, query: string) {
  if (!query.trim()) return text;
  return text;
}

function SearchSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="bg-white rounded-xl border p-4">
          <div className="flex gap-2 mb-2">
            <div className="h-5 w-16 bg-slate-200 rounded-full" />
            <div className="h-5 w-16 bg-slate-200 rounded-full" />
          </div>
          <div className="h-4 w-3/4 bg-slate-200 rounded mb-2" />
          <div className="h-3 w-full bg-slate-200 rounded" />
        </div>
      ))}
    </div>
  );
}
