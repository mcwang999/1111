"""Europe regional collector mini-agent."""

from airs.mini_agents.base_collector import BaseCollector


class EuropeCollector(BaseCollector):
    """Lightweight regional collector mini-agent for Europe."""

    REGION = "europe"
    REGION_LABEL = "Europe"
    COUNTRY_TERMS = "UK France Germany Italy Switzerland Spain"
    CITY_TERMS = "London Paris Milan Zurich Madrid"
    SEASONAL_TERMS = "Christmas Valentine wedding season tourism retail"
    AGENT_NAME = "europe_collector"

    REGION_RELEVANCE_TERMS = {
        "europe",
        "european",
        "uk",
        "united kingdom",
        "britain",
        "london",
        "france",
        "paris",
        "germany",
        "munich",
        "italy",
        "milan",
        "rome",
        "switzerland",
        "zurich",
        "geneva",
        "spain",
        "madrid",
        "barcelona",
        "netherlands",
        "amsterdam",
        "belgium",
        "brussels",
        "austria",
        "vienna",
        "scandinavia",
        "sweden",
        "norway",
        "denmark",
        "finland",
        "baselworld",
        "mipim",
    }

    CITY_QUERY_TERMS = ["London", "Paris"]

    RELEVANCE_PROMPT = (
        "RELEVANCE CRITERIA — keep a candidate if it relates to ANY of:\n"
        "- Jewellery, gold, diamonds, gems, jade, watches — including global shows "
        "(Baselworld, Vicenzaoro), trends, and brand news that affect the European market\n"
        "- Luxury retail and premium brands expanding, opening stores, or partnering "
        "in European markets (UK, France, Germany, Italy, Switzerland, Spain, etc.)\n"
        "- Competitor moves: any brand opening flagship stores, expanding retail, "
        "launching new collections, or forming partnerships in Europe\n"
        "- Product trends: design trends, consumer preferences, seasonal demand "
        "(Christmas, Valentine's, wedding season)\n"
        "- Platform & channels: high street retail, department stores, ecommerce, "
        "travel retail, social media trends affecting jewellery or luxury retail\n"
        "- Regulation: EU consumer protection, import duties, hallmarking requirements, "
        "retail policy changes\n"
        "- Macro & gold: gold price dynamics, currency volatility (EUR/GBP/CHF), "
        "economic outlook affecting jewellery demand in Europe\n"
        "- Tourism & hospitality developments that signal retail expansion "
        "(new luxury hotels, department store renovations, mixed-use developments)\n"
        "- Key companies: Chow Tai Fook, Pandora, LVMH, Richemont, Swatch Group, "
        "Cartier, Tiffany, Bulgari, Signet, Bucherer, local European chains\n\n"
        "DISCARD only candidates clearly unrelated to jewellery, luxury retail, "
        "or the European business landscape — such as pure tech (smartphones, SaaS), "
        "aviation, logistics, or politics with no retail angle."
    )