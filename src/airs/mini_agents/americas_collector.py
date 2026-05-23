"""Americas regional collector mini-agent."""

from airs.mini_agents.base_collector import BaseCollector


class AmericasCollector(BaseCollector):
    """Lightweight regional collector mini-agent for the Americas."""

    REGION = "americas"
    REGION_LABEL = "Americas"
    COUNTRY_TERMS = "USA Canada Brazil Mexico"
    CITY_TERMS = "New York Los Angeles Miami Toronto São Paulo"
    SEASONAL_TERMS = "Christmas Valentine Black Friday wedding season tourism retail"
    AGENT_NAME = "americas_collector"

    REGION_RELEVANCE_TERMS = {
        "americas",
        "usa",
        "united states",
        "us",
        "america",
        "new york",
        "los angeles",
        "miami",
        "las vegas",
        "chicago",
        "houston",
        "san francisco",
        "canada",
        "toronto",
        "vancouver",
        "brazil",
        "são paulo",
        "sao paulo",
        "rio",
        "mexico",
        "mexico city",
        "latin america",
        "latam",
        "caribbean",
        "thanksgiving",
        "black friday",
        "cyber monday",
        "super bowl",
    }

    CITY_QUERY_TERMS = ["New York", "USA"]

    RELEVANCE_PROMPT = (
        "RELEVANCE CRITERIA — keep a candidate if it relates to ANY of:\n"
        "- Jewellery, gold, diamonds, gems, jade, watches — including global shows "
        "(JCK Las Vegas, Couture), trends, and brand news that affect the Americas market\n"
        "- Luxury retail and premium brands expanding, opening stores, or partnering "
        "in the Americas (USA, Canada, Brazil, Mexico)\n"
        "- Competitor moves: any brand opening flagship stores, expanding retail, "
        "launching new collections, or forming partnerships in the Americas\n"
        "- Product trends: design trends, consumer preferences, seasonal demand "
        "(Christmas, Valentine's, Black Friday, wedding season)\n"
        "- Platform & channels: mall retail, department stores (Nordstrom, Neiman Marcus), "
        "ecommerce, social media trends affecting jewellery or luxury retail\n"
        "- Regulation: import duties, consumer protection (FTC), retail policy changes\n"
        "- Macro & gold: gold price dynamics, USD volatility, economic outlook "
        "affecting jewellery demand in the Americas\n"
        "- Tourism & hospitality developments that signal retail expansion "
        "(new luxury hotels, malls, mixed-use developments)\n"
        "- Key companies: Chow Tai Fook, Signet, Tiffany, Pandora, LVMH, Richemont, "
        "Cartier, Bulgari, David Yurman, local Americas chains\n\n"
        "DISCARD only candidates clearly unrelated to jewellery, luxury retail, "
        "or the Americas business landscape — such as pure tech (smartphones, SaaS), "
        "aviation, logistics, or politics with no retail angle."
    )