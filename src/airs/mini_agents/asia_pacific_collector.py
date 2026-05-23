"""Asia Pacific regional collector mini-agent."""

from airs.mini_agents.base_collector import BaseCollector


class AsiaPacificCollector(BaseCollector):
    """Lightweight regional collector mini-agent for Asia Pacific."""

    REGION = "asia_pacific"
    REGION_LABEL = "Asia Pacific"
    COUNTRY_TERMS = "Singapore Malaysia Thailand Vietnam Indonesia Philippines"
    CITY_TERMS = "Singapore Bangkok Ho Chi Minh Jakarta Manila"
    SEASONAL_TERMS = "Lunar New Year Songkran wedding season tourism retail"
    AGENT_NAME = "asia_pacific_collector"

    REGION_RELEVANCE_TERMS = {
        "asia pacific",
        "asia-pacific",
        "apac",
        "southeast asia",
        "asean",
        "singapore",
        "malaysia",
        "kuala lumpur",
        "thailand",
        "bangkok",
        "vietnam",
        "ho chi minh",
        "hanoi",
        "indonesia",
        "jakarta",
        "philippines",
        "manila",
        "australia",
        "sydney",
        "melbourne",
        "new zealand",
        "auckland",
        "lunar new year",
        "songkran",
    }

    CITY_QUERY_TERMS = ["Singapore", "Bangkok"]

    RELEVANCE_PROMPT = (
        "RELEVANCE CRITERIA — keep a candidate if it relates to ANY of:\n"
        "- Jewellery, gold, diamonds, gems, jade, watches — including global shows, "
        "trends, and brand news that affect the Asia Pacific market\n"
        "- Luxury retail and premium brands expanding, opening stores, or partnering "
        "in Asia Pacific markets (Singapore, Malaysia, Thailand, Vietnam, Indonesia, Philippines, Australia)\n"
        "- Competitor moves: any brand opening flagship stores, expanding retail, "
        "launching new collections, or forming partnerships in the region\n"
        "- Product trends: design trends, consumer preferences, seasonal demand "
        "(Lunar New Year, Songkran, wedding season)\n"
        "- Platform & channels: mall retail, ecommerce, travel retail (Changi, Suvarnabhumi), "
        "social media trends affecting jewellery or luxury retail\n"
        "- Regulation: import duties, consumer protection, retail policy changes in APAC\n"
        "- Macro & gold: gold price dynamics, currency volatility, economic outlook "
        "affecting jewellery demand in Asia Pacific\n"
        "- Tourism & hospitality developments that signal retail expansion "
        "(new luxury hotels, malls, mixed-use developments)\n"
        "- Key companies: Chow Tai Fook, Pandora, LVMH, Richemont, Swatch Group, "
        "Cartier, Tiffany, Bulgari, Signet, Malabar Gold, local APAC chains\n\n"
        "DISCARD only candidates clearly unrelated to jewellery, luxury retail, "
        "or the Asia Pacific business landscape — such as pure tech (smartphones, SaaS), "
        "aviation, logistics, or politics with no retail angle."
    )