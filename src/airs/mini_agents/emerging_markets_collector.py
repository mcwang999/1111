"""Emerging markets regional collector mini-agent."""

from airs.mini_agents.base_collector import BaseCollector


class EmergingMarketsCollector(BaseCollector):
    """Lightweight regional collector mini-agent for emerging markets."""

    REGION = "emerging_markets"
    REGION_LABEL = "Emerging Markets"
    COUNTRY_TERMS = "India Turkey Egypt South Africa Nigeria Kenya"
    CITY_TERMS = "Mumbai Istanbul Cairo Johannesburg Lagos Nairobi"
    SEASONAL_TERMS = "Diwali Akshaya Tritiya Eid wedding season monsoon retail"
    AGENT_NAME = "emerging_markets_collector"

    REGION_RELEVANCE_TERMS = {
        "emerging market",
        "emerging markets",
        "india",
        "mumbai",
        "delhi",
        "bengaluru",
        "chennai",
        "kolkata",
        "hyderabad",
        "turkey",
        "istanbul",
        "egypt",
        "cairo",
        "south africa",
        "johannesburg",
        "cape town",
        "nigeria",
        "lagos",
        "kenya",
        "nairobi",
        "morocco",
        "casablanca",
        "pakistan",
        "karachi",
        "bangladesh",
        "dhaka",
        "vietnam",
        "diwali",
        "akshaya tritiya",
        "dhanteras",
        "brics",
    }

    CITY_QUERY_TERMS = ["Mumbai", "India"]

    RELEVANCE_PROMPT = (
        "RELEVANCE CRITERIA — keep a candidate if it relates to ANY of:\n"
        "- Jewellery, gold, diamonds, gems, jade, watches — including global shows, "
        "trends, and brand news that affect emerging markets\n"
        "- Luxury retail and premium brands expanding, opening stores, or partnering "
        "in emerging markets (India, Turkey, Egypt, South Africa, Nigeria, Kenya, etc.)\n"
        "- Competitor moves: any brand opening flagship stores, expanding retail, "
        "launching new collections, or forming partnerships in emerging markets\n"
        "- Product trends: design trends, consumer preferences, seasonal demand "
        "(Diwali, Akshaya Tritiya, Eid, wedding season, Dhanteras)\n"
        "- Platform & channels: mall retail, ecommerce, travel retail, social media "
        "trends affecting jewellery or luxury retail in emerging markets\n"
        "- Regulation: import duties, consumer protection, retail policy changes, "
        "hallmarking requirements\n"
        "- Macro & gold: gold price dynamics, currency volatility (INR, TRY, ZAR, EGP), "
        "economic outlook affecting jewellery demand\n"
        "- Cultural gold demand: India's gold import policy, wedding gold demand, "
        "central bank gold reserves in emerging economies\n"
        "- Key companies: Chow Tai Fook, Titan/Tanishq, Malabar Gold, Kalyan Jewellers, "
        "Cartier, Pandora, local emerging market chains\n\n"
        "DISCARD only candidates clearly unrelated to jewellery, luxury retail, "
        "or emerging markets business landscape — such as pure tech (smartphones, SaaS), "
        "aviation, logistics, or politics with no retail angle."
    )