"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { ApiResponse, Document } from "@/lib/types";
import {
  AGENT_LABELS,
  DOC_TYPE_LABELS,
  IMPACT_TAG_LABELS,
  REGION_LABELS,
  TOPIC_LABELS,
  formatShortDateTime,
  labelFor,
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
  const docType = searchParams.get("doc_type") || "cards";
  const page = parseInt(searchParams.get("page") || "1", 10);

  const [data, setData] = useState<ApiResponse<Document> | null>(null);
  const [input, setInput] = useState(q);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (!q) {
        setData(null);
        return;
      }

      setLoading(true);
      setError("");
      const params = new URLSearchParams({ q, limit: "20", doc_type: docType, page: String(page) });

      fetch(`/api/search?${params}`)
        .then((res) => {
          if (!res.ok) throw new Error("搜索失败");
          return res.json();
        })
        .then((json) => setData(json as ApiResponse<Document>))
        .catch((err) => setError(err instanceof Error ? err.message : "搜索失败"))
        .finally(() => setLoading(false));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [q, docType, page]);

  const doSearch = (event: React.FormEvent) => {
    event.preventDefault();
    const params = new URLSearchParams();
    if (input.trim()) params.set("q", input.trim());
    if (docType !== "cards") params.set("doc_type", docType);
    router.push(`/search?${params}`);
  };

  const setDocType = (value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value === "cards") params.delete("doc_type");
    else params.set("doc_type", value);
    params.set("page", "1");
    router.push(`/search?${params}`);
  };

  const totalPages = data ? Math.ceil(data.count / data.limit) : 0;

  return (
    <div className="space-y-5">
      <section className="border-b border-neutral-200 pb-5">
        <h1 className="text-2xl font-semibold text-neutral-950">搜索</h1>
        <p className="mt-1 text-sm text-neutral-600">搜索情报卡片和原始来源的标题与正文。</p>
      </section>

      <form onSubmit={doSearch} className="grid gap-3 rounded-lg border border-neutral-200 bg-white p-4 md:grid-cols-[minmax(0,1fr)_180px_auto]">
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="输入关键词..."
          className="rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        />
        <select
          value={docType}
          onChange={(event) => setDocType(event.target.value)}
          className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm"
        >
          <option value="cards">全部卡片</option>
          <option value="intel_card">市场情报</option>
          <option value="social_signal_card">社媒信号</option>
          <option value="raw_source">原始来源</option>
        </select>
        <button
          type="submit"
          className="rounded-md bg-neutral-900 px-5 py-2 text-sm font-medium text-white hover:bg-neutral-700"
        >
          搜索
        </button>
      </form>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      ) : loading ? (
        <SearchSkeleton />
      ) : !q ? (
        <div className="rounded-lg border border-neutral-200 bg-white p-10 text-center text-sm text-neutral-500">
          输入关键词开始搜索
        </div>
      ) : !data || data.data.length === 0 ? (
        <div className="rounded-lg border border-neutral-200 bg-white p-10 text-center text-sm text-neutral-500">
          未找到与“{q}”相关的结果
        </div>
      ) : (
        <>
          <p className="text-sm text-neutral-500">
            “{q}”共 {data.count} 条结果
          </p>
          <div className="space-y-3">
            {data.data.map((doc) => (
              <SearchResult key={doc.id} doc={doc} />
            ))}
          </div>
          {totalPages > 1 && (
            <div className="flex justify-center gap-2 pt-2">
              <PageButton disabled={page <= 1} onClick={() => goPage(router, searchParams, page - 1)}>
                上一页
              </PageButton>
              <span className="px-3 py-1.5 text-sm text-neutral-500">
                {page} / {totalPages}
              </span>
              <PageButton disabled={page >= totalPages} onClick={() => goPage(router, searchParams, page + 1)}>
                下一页
              </PageButton>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function SearchResult({ doc }: { doc: Document }) {
  const meta = doc.metadata || {};
  const tags = meta.impact_tags || [];
  const href = doc.doc_type === "raw_source" ? doc.source_url || "#" : `/cards/${doc.id}`;

  return (
    <ResultLink href={href} external={doc.doc_type === "raw_source"}>
      <ResultBody doc={doc} tags={tags} />
    </ResultLink>
  );
}

function ResultLink({
  href,
  external,
  children,
}: {
  href: string;
  external: boolean;
  children: React.ReactNode;
}) {
  const className =
    "block rounded-lg border border-neutral-200 bg-white p-4 hover:border-neutral-400 hover:bg-neutral-50";

  if (external) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
        {children}
      </a>
    );
  }

  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}

function ResultBody({ doc, tags }: { doc: Document; tags: string[] }) {
  const meta = doc.metadata || {};

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <Chip>{labelFor(DOC_TYPE_LABELS, doc.doc_type)}</Chip>
        {meta.region && <Chip>{labelFor(REGION_LABELS, meta.region)}</Chip>}
        {meta.topic && <Chip>{labelFor(TOPIC_LABELS, meta.topic)}</Chip>}
        <span className="ml-auto text-xs text-neutral-500">
          {labelFor(AGENT_LABELS, doc.created_by_agent)} · {formatShortDateTime(doc.created_at)}
        </span>
      </div>
      <h2 className="mt-2 line-clamp-2 text-sm font-semibold text-neutral-950">{doc.title}</h2>
      <p className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-600">{doc.content}</p>
      {tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {tags.map((tag) => (
            <Chip key={tag}>{labelFor(IMPACT_TAG_LABELS, tag)}</Chip>
          ))}
        </div>
      )}
    </>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-md border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-xs font-medium text-neutral-700">
      {children}
    </span>
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

function goPage(
  router: ReturnType<typeof useRouter>,
  searchParams: ReturnType<typeof useSearchParams>,
  page: number,
) {
  const params = new URLSearchParams(searchParams.toString());
  params.set("page", String(page));
  router.push(`/search?${params}`);
}

function SearchSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {[1, 2, 3, 4].map((item) => (
        <div key={item} className="h-32 rounded-lg border border-neutral-200 bg-white p-4">
          <div className="mb-2 flex gap-2">
            <div className="h-5 w-16 rounded-md bg-neutral-200" />
            <div className="h-5 w-20 rounded-md bg-neutral-200" />
          </div>
          <div className="mb-2 h-4 w-3/4 rounded bg-neutral-200" />
          <div className="h-3 w-full rounded bg-neutral-200" />
        </div>
      ))}
    </div>
  );
}
