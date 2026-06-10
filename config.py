import os
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Singapore")
SHEETS_URL = os.getenv("SHEETS_URL")
SHEETS_SECRET = os.getenv("SHEETS_SECRET")

API_BASKETBALL_BASE = "https://v1.basketball.api-sports.io"
API_HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

EDGE_THRESHOLD = 4.0
MIN_CONFIDENCE = 54
MIN_MODELS_AGREE = 3
RL_MIN_CONFIDENCE = 65.0

LEAGUE_TIERS = {
    # Tier 1 — Active now, good odds coverage
    13:  {"name": "WNBA",           "country": "USA",         "tier": 1},
    359: {"name": "Euroleague W",   "country": "Europe",      "tier": 1},
    360: {"name": "EuroCup W",      "country": "Europe",      "tier": 1},
    125: {"name": "WCBA",           "country": "China",       "tier": 1},
    # Tier 2 — Active, some odds coverage
    246: {"name": "W League",       "country": "Japan",       "tier": 2},
    268: {"name": "WSBL",           "country": "Taiwan",      "tier": 2},
    270: {"name": "TKBL",           "country": "Turkey",      "tier": 2},
    41:  {"name": "DBBL",           "country": "Germany",     "tier": 2},
    234: {"name": "A1 Women",       "country": "Greece",      "tier": 2},
    232: {"name": "Ligue 2 W",      "country": "France",      "tier": 2},
    25:  {"name": "Top Division W", "country": "Belgium",     "tier": 2},
    240: {"name": "WBL",            "country": "Israel",      "tier": 2},
    256: {"name": "NBL Women",      "country": "New Zealand", "tier": 2},
    # Tier 3 — Active, thin odds
    211: {"name": "NBL1 Central W", "country": "Australia",   "tier": 3},
    216: {"name": "NBL1 East W",    "country": "Australia",   "tier": 3},
    208: {"name": "NBL1 North W",   "country": "Australia",   "tier": 3},
    210: {"name": "NBL1 South W",   "country": "Australia",   "tier": 3},
    213: {"name": "NBL1 West W",    "country": "Australia",   "tier": 3},
    109: {"name": "SLB Women",      "country": "UK",          "tier": 3},
    260: {"name": "LFB Women",      "country": "Portugal",    "tier": 3},
    255: {"name": "WBL",            "country": "Netherlands", "tier": 3},
    165: {"name": "Spanish Cup W",  "country": "Spain",       "tier": 3},
    243: {"name": "Serie A2 W N",   "country": "Italy",       "tier": 3},
    244: {"name": "Serie A2 W S",   "country": "Italy",       "tier": 3},
    247: {"name": "Championship W", "country": "Kazakhstan",  "tier": 3},
    265: {"name": "1. ZLS Women",   "country": "Serbia",      "tier": 3},
    257: {"name": "Prva Liga W",    "country": "Macedonia",   "tier": 3},
    230: {"name": "I Divisioona W", "country": "Finland",     "tier": 3},
    183: {"name": "AWBL Women",     "country": "Austria",     "tier": 3},
}

TIER_FACTORS = {1: 1.0, 2: 0.85, 3: 0.70}

# League average totals (points per game both teams combined)
LEAGUE_AVG_TOTALS = {
    13:  160.0,  # WNBA
    359: 150.0,  # Euroleague W
    360: 148.0,  # EuroCup W
    125: 155.0,  # WCBA
    246: 145.0,  # W League Japan
    268: 148.0,  # WSBL Taiwan
    270: 152.0,  # TKBL Turkey
    41:  152.0,  # DBBL Germany
    234: 148.0,  # A1 Greece
}
DEFAULT_AVG_TOTAL = 150.0
