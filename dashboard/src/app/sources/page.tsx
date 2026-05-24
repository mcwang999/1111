"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { ApiResponse, Document } from "@/lib/types";
import {
  AGENT_LABELS,
  REGION_LABELS,
  formatShortDateTime,
  labelFor,
} from "@/lib/types";

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
  const [error, setError] = useState("");

  const agent = searchParams.get("created_by_agent") || "";
  const page = parseInt(searchParams.get("page") || "1", 10);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({
      doc_type: "raw_source",
      limit: "30",
      sort: "created_at",
      dir: "desc",
      page: String(page),
    });
    if (agent) params.set("created_by_agent", agent);

    try {
      const res = await fetch(`/api/documents?${params}`);
      if (!res.ok) throw new Error("来源数据加载失败");
      setData((await res.json()) as ApiResponse<Document>);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [agent, page]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchData]);

  const setFilter = (key: string, value: string, resetPage = true) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    if (resetPage) params.set("page", "1");
    router.push(`/sources?${params}`);
  };

  const totalPages = data ? Math.ceil(data.count / data.limit) : 0;

  return (
    <div className="space-y-5">
      <section className="border-b border-neutral-200 pb-5">
        <h1 className="text-2xl font-semibold text-neutral-950">原始来源</h1>
        <p className="mt-1 text-sm text-neutral-600">
          查看采集到的原始内容，用于追溯情报卡片的来源和时间。
        </p>
      </section>

      <section className="rounded-lg border border-neutral-200 bg-white p-4">
        <label className="flex max-w-xs flex-col gap-1">
          <span className="text-xs font-medium text-neutral-500">Agent</span>
          <select
            className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm"
            value={agent}
            onChange={(event) => setFilter("created_by_agent", event.target.value)}
          >
            <option value="">全部 Agent</option>
            {ALL_AGENTS.map((key) => (
              <option key={key} value={key}>
                {labelFor(AGENT_LABELS, key)}
              </option>
            ))}
          </select>
        </label>
      </section>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      ) : loading ? (
        <SourcesSkeleton />
      ) : !data || data.data.length === 0 ? (
        <div className="rounded-lg border border-neutral-200 bg-white p-10 text-center text-sm text-neutral-500">
          暂无原始来源
        </div>
      ) : (
        <>
          <p className="text-sm text-neutral-500">共 {data.count} 条来源</p>
          <div className="space-y-2">
            {data.data.map((doc) => (
              <SourceRow key={doc.id} doc={doc} />
            ))}
          </div>
          {totalPages > 1 && (
            <div className="flex justify-center gap-2 pt-2">
              <PageButton disabled={page <= 1} onClick={() => setFilter("page", String(page - 1), false)}>
                上一页
              </PageButton>
              <span className="px-3 py-1.5 text-sm text-neutral-500">
                {page} / {totalPages}
              </span>
              <PageButton disabled={page >= totalPages} onClick={() => setFilter("page", String(page + 1), false)}>
                下一页
              </PageButton>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SourceRow({ doc }: { doc: Document }) {
  const meta = doc.metadata || {};
  const url = doc.source_url || meta.source_url || meta.url;

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-3">
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
        <span className="rounded-md border border-neutral-200 bg-neutral-50 px-2 py-0.5">
          {labelFor(REGION_LABELS, meta.region)}
        </span>
        <span>{meta.source_name || "未知来源"}</span>
        <span className="ml-auto">{formatShortDateTime(meta.published_at || doc.created_at)}</span>
      </div>
      <h2 className="line-clamp-1 text-sm font-medium text-neutral-950">{doc.title}</h2>
      <p className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-600">{doc.content}</p>
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-xs font-medium text-blue-700 hover:text-blue-900"
        >
          查看原文
        </a>
      )}
    </div>
  );
}

function PageButton({
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
      className={`rounded-md border px-3 py-1.5 text-sm ${
        disabled
          ? "cursor-not-allowed border-neutral-200 text-neutral-300"
          : "border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-50"
      }`}
    >
      {children}
    </button>
  );
}

function SourcesSkeleton() {
  return (
    <div className="space-y-2 animate-pulse">
      {[1, 2, 3, 4, 5].map((item) => (
        <div key={item} className="h-24 rounded-lg border border-neutral-200 bg-white p-3">
          <div className="mb-2 h-4 w-1/3 rounded bg-neutral-200" />
          <div className="mb-1 h-3 w-full rounded bg-neutral-200" />
          <div className="h-3 w-2/3 rounded bg-neutral-200" />
        </div>
      ))}
    </div>
  );
}
