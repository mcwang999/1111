"""Feishu Briefing Agent for AIRS.

Queries Supabase for competition-related intel cards and social signals,
formats them into a Chinese Markdown daily strategic briefing, and sends
it via Feishu CLI (lark-cli).

Pipeline:
    1. Query Supabase for competition intel_cards & social_signal_cards
    2. Format into Chinese Markdown briefing
    3. Send via lark-cli im +messages-send --markdown

Usage::

    from airs.mini_agents.feishu_briefing_agent import FeishuBriefingAgent

    agent = FeishuBriefingAgent.from_config()
    result = agent.run(
        topic="competition",
        user_id="ou_xxx",  # Feishu user open_id
    )
    print(result)
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from airs.mini_agents.base_collector import SupabaseWriter, load_supabase_config


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class IntelItem:
    """A single intelligence item from Supabase."""
    id: str
    doc_type: str
    title: str
    content: str
    source_url: str
    metadata: dict[str, Any]
    created_at: str


@dataclass
class BriefingResult:
    """Result of sending a briefing via Feishu."""
    markdown_content: str
    items_count: int
    feishu_output: str
    success: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# Topic label mapping (Chinese)
# ---------------------------------------------------------------------------

TOPIC_LABELS_CN = {
    "competition": "竞品与市场动态",
    "product": "产品与消费趋势",
    "channel": "渠道与零售动态",
    "social": "社媒与消费者声音",
    "regulation": "政策与合规动态",
}

IMPACT_TAG_LABELS_CN = {
    "supply_chain": "供应链",
    "compliance": "合规",
    "cost": "成本",
    "pricing": "定价",
    "inventory": "库存",
    "logistics": "物流",
    "sourcing": "采购",
    "retail_operations": "零售运营",
    "consumer_demand": "消费需求",
    "brand_reputation": "品牌声誉",
    "gold_price": "金价",
}

VERTICAL_LABELS_CN = {
    "gold_jewellery": "黄金珠宝",
    "jade_colored_gems_cultural_jewellery": "玉石彩宝文化珠宝",
    "overseas_retail_channels": "海外零售渠道",
    "other": "其他",
}

SIGNAL_TYPE_LABELS_CN = {
    "trend": "趋势",
    "purchase_intent": "购买意向",
    "pain_point": "痛点",
    "brand_sentiment": "品牌情绪",
    "occasion": "场景",
    "pricing_value": "价格价值",
}

SENTIMENT_LABELS_CN = {
    "positive": "正面",
    "negative": "负面",
    "neutral": "中性",
    "mixed": "混合",
}


# ---------------------------------------------------------------------------
# Briefing formatter
# ---------------------------------------------------------------------------

def format_briefing_markdown(
    items: list[IntelItem],
    topic: str = "competition",
    date_str: str | None = None,
) -> str:
    """Format intel items into a Chinese Markdown briefing.

    Args:
        items: List of IntelItem objects from Supabase.
        topic: Topic key (e.g. "competition").
        date_str: Date string for the briefing header. Defaults to today.

    Returns:
        Chinese Markdown string suitable for Feishu message.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    topic_cn = TOPIC_LABELS_CN.get(topic, topic)

    # Group by doc_type
    intel_cards = [i for i in items if i.doc_type == "intel_card"]
    social_cards = [i for i in items if i.doc_type == "social_signal_card"]

    # Sort by importance/confidence score descending
    def sort_key(item: IntelItem) -> float:
        meta = item.metadata
        return max(
            meta.get("importance_score", 0) or 0,
            meta.get("confidence_score", 0) or 0,
        )

    intel_cards.sort(key=sort_key, reverse=True)
    social_cards.sort(key=sort_key, reverse=True)

    lines: list[str] = []
    lines.append(f"# 📋 每日战略简报 — {topic_cn}")
    lines.append(f"**{date_str}**")
    lines.append("")

    # --- Summary stats ---
    total = len(intel_cards) + len(social_cards)
    lines.append(f"今日共收录 **{total}** 条情报（情报卡 {len(intel_cards)} 条，社媒信号 {len(social_cards)} 条）")
    lines.append("")

    # --- Impact tag distribution ---
    all_tags: list[str] = []
    for item in items:
        all_tags.extend(item.metadata.get("impact_tags", []))
    if all_tags:
        from collections import Counter
        tag_counts = Counter(all_tags)
        lines.append("**影响领域分布：**")
        for tag, count in tag_counts.most_common(5):
            tag_cn = IMPACT_TAG_LABELS_CN.get(tag, tag)
            lines.append(f"- {tag_cn}：{count} 条")
        lines.append("")

    # --- Intel cards section ---
    if intel_cards:
        lines.append("---")
        lines.append("")
        for idx, card in enumerate(intel_cards[:10], 1):
            meta = card.metadata
            region = meta.get("region", "")
            vertical = VERTICAL_LABELS_CN.get(
                meta.get("strategic_vertical", ""), meta.get("strategic_vertical", "")
            )
            importance = meta.get("importance_score", 0) or 0
            confidence = meta.get("confidence_score", 0) or 0
            impact_tags = meta.get("impact_tags", [])
            impact_cn = "、".join(
                str(IMPACT_TAG_LABELS_CN.get(t, t)) for t in impact_tags[:3]
            )
            source_count = meta.get("source_count", 1) or 1
            published = meta.get("published_at", "")

            # Importance indicator
            if importance >= 0.8:
                level = "🔴 高重要"
            elif importance >= 0.5:
                level = "🟡 中重要"
            else:
                level = "🟢 低重要"

            lines.append(f"### {idx}. {card.title}")
            lines.append(f"> {level} | 置信度 {confidence:.0%} | 来源 {source_count} 条 | {published}")
            if region:
                lines.append(f"> 地区：{region} | 垂直：{vertical}")
            if impact_cn:
                lines.append(f"> 影响领域：{impact_cn}")
            if card.source_url:
                lines.append(f"> [查看原文]({card.source_url})")
            lines.append("")

    # --- Social signal cards section ---
    if social_cards:
        lines.append("---")
        lines.append("")
        for idx, card in enumerate(social_cards[:8], 1):
            meta = card.metadata
            signal_type = SIGNAL_TYPE_LABELS_CN.get(
                meta.get("signal_type", ""), meta.get("signal_type", "")
            )
            sentiment = SENTIMENT_LABELS_CN.get(
                meta.get("sentiment", ""), meta.get("sentiment", "")
            )
            platforms = "、".join(str(p) for p in meta.get("platforms", []))
            post_count = meta.get("post_count", 0) or 0

            lines.append(f"### {idx}. {card.title}")
            lines.append(f"> 📱 {signal_type} | 情绪：{sentiment} | 平台：{platforms} | 帖子数：{post_count}")
            if card.source_url:
                lines.append(f"> [查看原文]({card.source_url})")
            lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append("*本简报由 POLARIS 智能情报系统自动生成*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Feishu CLI sender
# ---------------------------------------------------------------------------

def send_feishu_markdown(
    markdown_content: str,
    user_id: str | None = None,
    chat_id: str | None = None,
    lark_cli_path: str = "lark-cli",
    as_bot: bool = True,
) -> str:
    """Send a Markdown message via lark-cli.

    Uses lark-cli's raw API mode to avoid all Windows command-line escaping
    issues. Writes the request JSON to a temp file, then calls:
        lark-cli api POST /open-apis/im/v1/messages --params <file> --data <file>

    Args:
        markdown_content: The Markdown text to send.
        user_id: Feishu user open_id (ou_xxx) for DM.
        chat_id: Feishu chat ID (oc_xxx) for group message.
        lark_cli_path: Path to lark-cli executable.
        as_bot: Whether to send as bot identity.

    Returns:
        stdout from lark-cli command.
    """
    import json
    import os
    import tempfile

    # Resolve lark-cli path (on Windows, subprocess may not find .cmd without full path)
    if sys.platform == "win32":
        import shutil
        resolved_cli = shutil.which(lark_cli_path) or lark_cli_path
        # On Windows, prefer the .cmd wrapper if available
        if not resolved_cli.endswith(".cmd"):
            cmd_path = shutil.which(lark_cli_path + ".cmd") or resolved_cli
        else:
            cmd_path = resolved_cli
    else:
        cmd_path = lark_cli_path

    receive_id = user_id or chat_id
    if not receive_id:
        raise ValueError("Must provide either user_id or chat_id")
    receive_id_type = "open_id" if user_id else "chat_id"

    # Build the API request payload
    params = {"receive_id_type": receive_id_type}
    data = {
        "receive_id": receive_id,
        "msg_type": "post",
        "content": json.dumps(
            {
                "zh_cn": {
                    "title": "每日战略简报",
                    "content": _markdown_to_post_lines(markdown_content),
                }
            },
            ensure_ascii=False,
        ),
    }

    # Write params and data to temp files in CWD (lark-cli requires relative paths for @file)
    pid = os.getpid()
    params_filename = f"feishu_params_{pid}.json"
    data_filename = f"feishu_data_{pid}.json"

    with open(params_filename, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False)

    with open(data_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    try:
        cmd = [
            cmd_path,
            "api",
            "POST",
            "/open-apis/im/v1/messages",
            "--params", f"@{params_filename}",
            "--data", f"@{data_filename}",
        ]
        if as_bot:
            cmd.extend(["--as", "bot"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"lark-cli api failed (exit {result.returncode}): {result.stderr or result.stdout}"
            )

        return result.stdout
    finally:
        for path in (params_filename, data_filename):
            try:
                os.unlink(path)
            except OSError:
                pass


def _markdown_to_post_lines(markdown_text: str) -> list[list[dict]]:
    """Convert markdown text to Feishu post message content lines.

    Feishu post format: list of lines, each line is a list of content elements.
    Supported element types: text (with optional bold/italic), a (link).

    For simplicity, we split by newlines and create text elements.
    Lines starting with # become bold text elements.
    Lines starting with > become quoted text elements.
    Lines starting with - become list items.
    Lines starting with --- become divider lines (empty line).
    """
    lines: list[list[dict]] = []

    for raw_line in markdown_text.split("\n"):
        line = raw_line.strip()

        if not line:
            # Empty line — skip (Feishu post handles spacing)
            continue

        if line == "---":
            # Horizontal rule — add an empty line
            lines.append([{"tag": "text", "text": "\n"}])
            continue

        if line.startswith("# "):
            # Heading — bold text
            text = line[2:].strip()
            lines.append([{"tag": "text", "text": text, "style": ["bold"]}])
            continue

        if line.startswith("## "):
            # Sub-heading — bold text
            text = line[3:].strip()
            lines.append([{"tag": "text", "text": text, "style": ["bold"]}])
            continue

        if line.startswith("### "):
            # Sub-sub-heading — bold text
            text = line[4:].strip()
            lines.append([{"tag": "text", "text": text, "style": ["bold"]}])
            continue

        if line.startswith("> "):
            # Quote — plain text with indent
            text = line[2:].strip()
            lines.append([{"tag": "text", "text": f"  {text}"}])
            continue

        if line.startswith("- "):
            # List item
            text = line[2:].strip()
            # Handle bold within list items
            elements = _parse_inline_formatting(text)
            lines.append([{"tag": "text", "text": "• "}] + elements)
            continue

        if line.startswith("*") and line.endswith("*") and not line.startswith("**"):
            # Italic line
            text = line.strip("*").strip()
            lines.append([{"tag": "text", "text": text, "style": ["italic"]}])
            continue

        # Regular line — parse inline formatting
        elements = _parse_inline_formatting(line)
        if elements:
            lines.append(elements)

    return lines


def _parse_inline_formatting(text: str) -> list[dict]:
    """Parse inline markdown formatting (bold, links) into Feishu post elements."""
    import re

    elements: list[dict] = []
    # Simple approach: split by markdown link patterns and bold patterns
    # Pattern: [text](url) → link element
    # Pattern: **text** → bold text element
    # Everything else → plain text element

    # Process links first, then bold within text segments
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    bold_pattern = re.compile(r'\*\*([^*]+)\*\*')

    pos = 0
    for match in link_pattern.finditer(text):
        # Add text before this link
        before = text[pos:match.start()]
        if before:
            # Process bold within the before text
            elements.extend(_process_bold_text(before))
        # Add the link
        elements.append({
            "tag": "a",
            "text": match.group(1),
            "href": match.group(2),
        })
        pos = match.end()

    # Add remaining text after last link
    remaining = text[pos:]
    if remaining:
        elements.extend(_process_bold_text(remaining))

    return elements


def _process_bold_text(text: str) -> list[dict]:
    """Process **bold** markers in text into Feishu elements."""
    import re

    elements: list[dict] = []
    bold_pattern = re.compile(r'\*\*([^*]+)\*\*')

    pos = 0
    for match in bold_pattern.finditer(text):
        # Add plain text before bold
        before = text[pos:match.start()]
        if before:
            elements.append({"tag": "text", "text": before})
        # Add bold text
        elements.append({"tag": "text", "text": match.group(1), "style": ["bold"]})
        pos = match.end()

    # Add remaining plain text
    remaining = text[pos:]
    if remaining:
        elements.append({"tag": "text", "text": remaining})

    return elements


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class FeishuBriefingAgent:
    """Queries Supabase for intel data, formats a Chinese briefing, and
    sends it via Feishu CLI."""

    def __init__(
        self,
        supabase_writer: SupabaseWriter,
        lark_cli_path: str = "lark-cli",
    ) -> None:
        self.supabase_writer = supabase_writer
        self.lark_cli_path = lark_cli_path

    @classmethod
    def from_config(cls, config_path: str | Path = ".config.yaml") -> FeishuBriefingAgent:
        config = load_supabase_config(config_path)
        if not config.get("url") or not config.get("service_role_key"):
            raise RuntimeError(
                "Missing Supabase config. Add supabase.url and "
                "supabase.service_role_key to .config.yaml."
            )
        writer = SupabaseWriter(
            url=config["url"],
            service_role_key=config["service_role_key"],
        )
        return cls(supabase_writer=writer)

    def fetch_intel_items(
        self,
        topic: str = "competition",
        limit: int = 20,
        hours: int = 168,  # 7 days
    ) -> list[IntelItem]:
        """Fetch intel_cards and social_signal_cards for a given topic from Supabase.

        Args:
            topic: Topic filter (e.g. "competition").
            limit: Max number of items to return.
            hours: Lookback window in hours.

        Returns:
            List of IntelItem objects.
        """
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        # Query intel_cards and social_signal_cards with topic filter
        # Use metadata->>topic filter and created_at cutoff
        query_params = {
            "select": "id,doc_type,title,content,source_url,metadata,created_at",
            "doc_type": "in.(intel_card,social_signal_card)",
            "metadata->>topic": f"eq.{topic}",
            "created_at": f"gte.{cutoff}",
            "order": "created_at.desc",
            "limit": str(limit),
        }

        response = self.supabase_writer.http_client.get(
            f"{self.supabase_writer.url}/rest/v1/documents",
            headers=self.supabase_writer._headers(),
            params=query_params,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Supabase query failed: {response.status_code} {response.text[:500]}"
            )

        rows = response.json()
        items: list[IntelItem] = []
        for row in rows:
            items.append(IntelItem(
                id=row.get("id", ""),
                doc_type=row.get("doc_type", ""),
                title=row.get("title", ""),
                content=row.get("content", ""),
                source_url=row.get("source_url", ""),
                metadata=row.get("metadata", {}),
                created_at=row.get("created_at", ""),
            ))

        return items

    def run(
        self,
        topic: str = "competition",
        user_id: str | None = None,
        chat_id: str | None = None,
        as_bot: bool = True,
        hours: int = 168,
        limit: int = 20,
        dry_run: bool = False,
    ) -> BriefingResult:
        """Run the full briefing pipeline: fetch → format → send.

        Args:
            topic: Topic key to filter (default: "competition").
            user_id: Feishu user open_id for DM.
            chat_id: Feishu chat ID for group message.
            as_bot: Send as bot identity.
            hours: Lookback window in hours (default: 168 = 7 days).
            limit: Max items to fetch.
            dry_run: If True, format but don't send.

        Returns:
            BriefingResult with markdown content and send status.
        """
        # 1. Fetch
        items = self.fetch_intel_items(topic=topic, limit=limit, hours=hours)
        print(f"[FeishuBriefingAgent] Fetched {len(items)} items for topic='{topic}'")

        if not items:
            markdown = format_briefing_markdown([], topic=topic)
            markdown += f"\n\n⚠️ 过去 {hours//24} 天内暂无「{TOPIC_LABELS_CN.get(topic, topic)}」相关情报。"
            return BriefingResult(
                markdown_content=markdown,
                items_count=0,
                feishu_output="",
                success=False,
                error="No items found",
            )

        # 2. Format
        markdown = format_briefing_markdown(items, topic=topic)

        if dry_run:
            print("[FeishuBriefingAgent] Dry run — skipping send")
            return BriefingResult(
                markdown_content=markdown,
                items_count=len(items),
                feishu_output="",
                success=True,
                error=None,
            )

        # 3. Send
        try:
            output = send_feishu_markdown(
                markdown_content=markdown,
                user_id=user_id,
                chat_id=chat_id,
                lark_cli_path=self.lark_cli_path,
                as_bot=as_bot,
            )
            print(f"[FeishuBriefingAgent] Sent briefing via Feishu")
            return BriefingResult(
                markdown_content=markdown,
                items_count=len(items),
                feishu_output=output,
                success=True,
                error=None,
            )
        except Exception as exc:
            print(f"[FeishuBriefingAgent] Failed to send: {exc}")
            return BriefingResult(
                markdown_content=markdown,
                items_count=len(items),
                feishu_output="",
                success=False,
                error=str(exc),
            )