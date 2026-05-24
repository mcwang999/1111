"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { ApiResponse, Document } from "@/lib/types";
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
  formatScore,
  formatShortDateTime,
  getBriefingStatus,
  getCardLastSeenAt,
  getCardPublishedAt,
  labelFor,
} from "@/lib/types";

const CARD_TYPE_OPTIONS = ["cards", "intel_card", "social_signal_card"];
const ALL_REGIONS = Object.keys(REGION_LABELS);
const ALL_TOPICS = Object.keys(TOPIC_LABELS);
const ALL_TAGS = Object.keys(IMPACT_TAG_LABELS);
const ALL_VERTICALS = Object.keys(VERTICAL_LABELS);
const ALL_AGENTS = Object.keys(AGENT_LABELS);
const ALL_STATUSES = Object.keys(BRIEFING_STATUS_LABELS);
const ALL_SIGNAL_TYPES = Object.keys(SIGNAL_TYPE_LABELS);

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
  const [error, setError] = useState("");

  const docType = searchParams.get("doc_type") || "cards";
  const region = searchParams.get("region") || "";
  const topic = searchParams.get("topic") || "";
  const tags = searchParams.get("impact_tags") || "";
  const vertical = searchParams.get("strategic_vertical") || "";
  const agent = searchParams.get("created_by_agent") || "";
  const briefingStatus = searchParams.get("briefing_status") || "";
  const signalType = searchParams.get("signal_type") || "";
  const sort = searchParams.get("sort") || "last_seen_at";
  const page = parseInt(searchParams.get("page") || "1", 10);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ doc_type: docType, limit: "20", sort, dir: "desc" });
    if (region) params.set("region", region);
    if (topic) params.set("topic", topic);
    if (tags) params.set("impact_tags", tags);
    if (vertical) params.set("strategic_vertical", vertical);
    if (agent) params.set("created_by_agent", agent);
    if (briefingStatus) params.set("briefing_status", briefingStatus);
    if (signalType) params.set("signal_type", signalType);
    params.set("page", String(page));

    try {
      const res = await fetch(`/api/documents?${params}`);
      if (!res.ok) throw new Error("情报卡片加载失败");
      const json = (await res.json()) as ApiResponse<Document>;
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [agent, briefingStatus, docType, page, region, signalType, sort, tags, topic, vertical]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchData]);

  const setFilter = (key: string, value: string, resetPage = true) => {
    const p = new URLSearchParams(searchParams.toString());
    if (key === "doc_type" && value === "cards") p.delete("doc_type");
    else if (value) p.set(key, value);
    else p.delete(key);
    if (resetPage) p.set("page", "1");
    router.push(`/cards?${p.toString()}`);
  };

  const totalPages = data ? Math.ceil(data.count / data.limit) : 0;

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-2 border-b border-neutral-200 pb-5 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-950">情报卡片流</h1>
          <p className="mt-1 text-sm text-neutral-600">
            市场情报和社媒信号统一监测，筛选结果会保存在 URL 中。
          </p>
        </div>
        <Link
          href="/"
          className="self-start rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-800 hover:bg-neutral-50 md:self-auto"
        >
          返回监测台
        </Link>
      </section>

      <section className="rounded-lg border border-neutral-200 bg-white p-4">
        <div className="mb-4 flex flex-wrap gap-2">
          {CARD_TYPE_OPTIONS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilter("doc_type", value)}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium ${
                docType === value
                  ? "border-neutral-900 bg-neutral-900 text-white"
                  : "border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-50"
              }`}
            >
              {labelFor(DOC_TYPE_LABELS, value)}
            </button>
          ))}
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <FilterSelect label="地区" value={region} onChange={(v) => setFilter("region", v)} options={ALL_REGIONS} optionLabels={REGION_LABELS} placeholder="全部地区" />
          <FilterSelect label="主题" value={topic} onChange={(v) => setFilter("topic", v)} options={ALL_TOPICS} optionLabels={TOPIC_LABELS} placeholder="全部主题" />
          <FilterSelect label="影响标签" value={tags} onChange={(v) => setFilter("impact_tags", v)} options={ALL_TAGS} optionLabels={IMPACT_TAG_LABELS} placeholder="全部标签" />
          <FilterSelect label="垂直领域" value={vertical} onChange={(v) => setFilter("strategic_vertical", v)} options={ALL_VERTICALS} optionLabels={VERTICAL_LABELS} placeholder="全部领域" />
          <FilterSelect label="简报状态" value={briefingStatus} onChange={(v) => setFilter("briefing_status", v)} options={ALL_STATUSES} optionLabels={BRIEFING_STATUS_LABELS} placeholder="全部状态" />
          <FilterSelect label="信号类型" value={signalType} onChange={(v) => setFilter("signal_type", v)} options={ALL_SIGNAL_TYPES} optionLabels={SIGNAL_TYPE_LABELS} placeholder="全部信号" />
          <FilterSelect label="Agent" value={agent} onChange={(v) => setFilter("created_by_agent", v)} options={ALL_AGENTS} optionLabels={AGENT_LABELS} placeholder="全部 Agent" />
          <FilterSelect
            label="排序"
            value={sort}
            onChange={(v) => setFilter("sort", v)}
            options={["last_seen_at", "published_at", "importance_score", "relevance_score", "confidence_score", "created_at"]}
            optionLabels={{
              last_seen_at: "最近出现",
              published_at: "发布时间",
              importance_score: "重要度",
              relevance_score: "相关度",
              confidence_score: "置信度",
              created_at: "写入时间",
            }}
            placeholder="默认排序"
          />
        </div>
      </section>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      ) : loading ? (
        <CardsSkeleton />
      ) : !data || data.data.length === 0 ? (
        <div className="rounded-lg border border-neutral-200 bg-white p-10 text-center text-sm text-neutral-500">
          暂无匹配的情报卡片
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between text-sm text-neutral-500">
            <p>
              共 {data.count} 条结果，第 {data.page}/{Math.max(1, totalPages)} 页
            </p>
          </div>
          <div className="space-y-3">
            {data.data.map((doc) => (
              <CardItem key={doc.id} doc={doc} />
            ))}
          </div>
          {totalPages > 1 && (
            <div className="flex justify-center gap-2 pt-2">
              <PageBtn
                disabled={page <= 1}
                onClick={() => setFilter("page", String(page - 1), false)}
              >
                上一页
              </PageBtn>
              <span className="px-3 py-1.5 text-sm text-neutral-500">
                {page} / {totalPages}
              </span>
              <PageBtn
                disabled={page >= totalPages}
                onClick={() => setFilter("page", String(page + 1), false)}
              >
                下一页
              </PageBtn>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function CardItem({ doc }: { doc: Document }) {
  const meta = doc.metadata || {};
  const isSocial = doc.doc_type === "social_signal_card";
  const tags = meta.impact_tags || [];
  const status = getBriefingStatus(doc);
  const score = meta.importance_score ?? meta.relevance_score ?? meta.confidence_score;

  return (
    <Link
      href={`/cards/${doc.id}`}
      className="block rounded-lg border border-neutral-200 bg-white p-4 hover:border-neutral-400 hover:bg-neutral-50"
    >
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

      <h2 className="mt-3 line-clamp-2 text-base font-semibold text-neutral-950">{doc.title}</h2>
      <p className="mt-1 line-clamp-2 text-sm leading-6 text-neutral-600">{doc.content}</p>

      <div className="mt-3 grid gap-2 text-xs text-neutral-500 md:grid-cols-4">
        <MetaLine label={isSocial ? "平台" : "地区"} value={isSocial ? formatList(meta.platforms) : labelFor(REGION_LABELS, meta.region)} />
        <MetaLine label={isSocial ? "覆盖地区" : "垂直领域"} value={isSocial ? formatList(meta.regions?.map((r) => labelFor(REGION_LABELS, r))) : labelFor(VERTICAL_LABELS, meta.strategic_vertical)} />
        <MetaLine label={isSocial ? "情绪" : "来源数"} value={isSocial ? labelFor(SENTIMENT_LABELS, meta.sentiment) : String(meta.source_count ?? "-")} />
        <MetaLine label={isSocial ? "帖子数" : "分数"} value={isSocial ? String(meta.post_count ?? "-") : formatScore(score)} />
        <MetaLine label="发布时间" value={formatShortDateTime(getCardPublishedAt(doc))} />
        <MetaLine label="Agent" value={labelFor(AGENT_LABELS, doc.created_by_agent)} />
      </div>

      {tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <Chip key={tag} tone="slate">
              {labelFor(IMPACT_TAG_LABELS, tag)}
            </Chip>
          ))}
        </div>
      )}
    </Link>
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
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-neutral-500">{label}</span>
      <select
        className="min-w-0 rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 focus:border-blue-500 focus:outline-none"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{placeholder}</option>
        {options.map((key) => (
          <option key={key} value={key}>
            {optionLabels[key] || key}
          </option>
        ))}
      </select>
    </label>
  );
}

function MetaLine({ label, value }: { label: string; value: string }) {
  return (
    <p>
      <span className="text-neutral-400">{label}：</span>
      <span className="text-neutral-700">{value}</span>
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

function formatList(values?: string[]) {
  if (!values || values.length === 0) return "未标注";
  return values.join(" / ");
}

function CardsSkeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      {[1, 2, 3, 4, 5].map((item) => (
        <div key={item} className="h-40 rounded-lg border border-neutral-200 bg-white p-4">
          <div className="mb-3 flex gap-2">
            <div className="h-5 w-16 rounded-md bg-neutral-200" />
            <div className="h-5 w-20 rounded-md bg-neutral-200" />
          </div>
          <div className="mb-2 h-5 w-2/3 rounded bg-neutral-200" />
          <div className="mb-1 h-4 w-full rounded bg-neutral-200" />
          <div className="h-4 w-1/2 rounded bg-neutral-200" />
        </div>
      ))}
    </div>
  );
}
