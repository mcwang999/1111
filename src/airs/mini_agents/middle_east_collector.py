"""Middle East regional collector mini-agent."""

from airs.mini_agents.base_collector import BaseCollector


class MiddleEastCollector(BaseCollector):
    """Lightweight regional collector mini-agent for the Middle East."""

    REGION = "middle_east"
    REGION_LABEL = "Middle East"
    COUNTRY_TERMS = "UAE Saudi Arabia Qatar Kuwait"
    CITY_TERMS = "Dubai Abu Dhabi Riyadh Doha"
    SEASONAL_TERMS = "Ramadan Eid wedding demand tourism retail"
    AGENT_NAME = "middle_east_collector"

    REGION_RELEVANCE_TERMS = {
        "middle east",
        "uae",
        "dubai",
        "abu dhabi",
        "saudi",
        "saudi arabia",
        "riyadh",
        "qatar",
        "doha",
        "kuwait",
        "gulf",
        "gcc",
        "mena",
        "ramadan",
        "eid",
    }

    CITY_QUERY_TERMS = ["Dubai", "UAE"]

    RELEVANCE_PROMPT = (
        "RELEVANCE CRITERIA — keep a candidate if it relates to ANY of:\n"
        "- Jewellery, gold, diamonds, gems, jade, watches — including global shows, "
        "trends, and brand news that affect the Middle East market\n"
        "- Luxury retail and premium brands expanding, opening stores, or partnering "
        "in the Middle East / Gulf / MENA region\n"
        "- Competitor moves: any brand opening flagship stores, expanding retail, "
        "launching new collections, or forming partnerships in the region\n"
        "- Product trends: design trends, consumer preferences, seasonal demand "
        "(Ramadan, Eid, wedding season)\n"
        "- Platform & channels: mall retail, ecommerce, travel retail, social media "
        "trends affecting jewellery or luxury retail\n"
        "- Regulation: import duties, consumer protection, retail policy changes\n"
        "- Macro & gold: gold price dynamics, currency volatility, economic outlook "
        "affecting jewellery demand\n"
        "- Hospitality & tourism developments that signal retail expansion "
        "(new luxury hotels, malls, mixed-use developments in the Gulf)\n"
        "- Key companies: Chow Tai Fook, Pandora, LVMH, Richemont, Swatch Group, "
        "Cartier, Tiffany, Bulgari, Signet, Malabar Gold, Damas, etc.\n\n"
        "DISCARD only candidates clearly unrelated to jewellery, luxury retail, "
        "or the Middle East business landscape — such as pure tech (smartphones, SaaS), "
        "aviation, logistics, or politics with no retail angle."
    )