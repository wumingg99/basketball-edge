import requests
from datetime import datetime, timedelta
import pytz
from config import API_BASKETBALL_BASE, API_HEADERS, TIMEZONE, LEAGUE_TIERS, LEAGUE_AVG_TOTALS, DEFAULT_AVG_TOTAL

_cache = {}
_games_data_cache = []

def get_league_avg(league_id):
    return LEAGUE_AVG_TOTALS.get(league_id, DEFAULT_AVG_TOTAL)

def get_todays_games():
    tz = pytz.timezone(TIMEZONE)
    sgt_now = datetime.now(tz)
    # WNBA games finish ~midnight ET = noon SGT next day
    # Switch to next day after 1PM SGT (1AM ET, after all games done)
    et_tz = pytz.timezone("America/New_York")
    et_now = datetime.now(et_tz)
    if et_now.hour >= 23:
        today = (sgt_now + timedelta(days=1)).strftime("%Y-%m-%d")
        _cache["showing_next_day"] = True
    else:
        today = sgt_now.strftime("%Y-%m-%d")
        _cache["showing_next_day"] = False
    if "games" in _cache and _cache.get("games_date") == today:
        return _cache["games"]
    games = []
    for league_id, league_info in LEAGUE_TIERS.items():
        try:
            url = f"{API_BASKETBALL_BASE}/games"
            params = {"league": league_id, "season": sgt_now.year, "date": today}
            r = requests.get(url, headers=API_HEADERS, params=params, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            for game in data.get("response", []):
                status = game.get("status", {}).get("long", "")
                if status in ["Postponed", "Cancelled"]:
                    continue
                home = game.get("teams", {}).get("home", {})
                away = game.get("teams", {}).get("away", {})
                date_str = game.get("date", "")
                game_time_sgt = ""
                if date_str:
                    try:
                        from datetime import timezone
                        utc_dt = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00"))
                        sgt_dt = utc_dt.astimezone(tz)
                        game_time_sgt = sgt_dt.strftime("%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        pass
                scores = game.get("scores", {})
                home_score = scores.get("home", {}).get("total")
                away_score = scores.get("away", {}).get("total")
                games.append({
                    "game_id": game.get("id"),
                    "date": today,
                    "league_id": league_id,
                    "league_name": league_info["name"],
                    "league_tier": league_info["tier"],
                    "country": league_info["country"],
                    "home_team": home.get("name", "Unknown"),
                    "away_team": away.get("name", "Unknown"),
                    "home_id": home.get("id"),
                    "away_id": away.get("id"),
                    "status": status,
                    "start_time_sgt": game_time_sgt,
                    "home_score": home_score,
                    "away_score": away_score,
                })
        except Exception as e:
            print(f"Error fetching league {league_id}: {e}")
            continue
    # Deduplicate
    seen = set()
    unique = []
    for g in games:
        gid = g.get("game_id")
        if gid not in seen:
            seen.add(gid)
            unique.append(g)
    games = unique
    print(f"Fetched {len(games)} basketball games today")
    _cache["games"] = games
    _cache["games_date"] = today
    return games

def get_team_stats(team_id, league_id, season=None):
    if not team_id:
        return _default_stats()
    cache_key = f"team_{team_id}_{league_id}"
    if cache_key in _cache:
        return _cache[cache_key]
    result = _default_stats()
    try:
        tz = pytz.timezone(TIMEZONE)
        season = season or datetime.now(tz).year
        url = f"{API_BASKETBALL_BASE}/teams/statistics"
        params = {"league": league_id, "season": season, "team": team_id}
        r = requests.get(url, headers=API_HEADERS, params=params, timeout=10)
        if r.status_code != 200:
            return result
        data = r.json().get("response", {})
        if not data:
            return result
        games = data.get("games", {})
        points = data.get("points", {})
        wins = games.get("wins", {})
        played = games.get("played", {})
        games_played = int(played.get("all", 1) or 1)
        wins_all = int(wins.get("all", 0) or 0)
        pts_for = points.get("for", {})
        pts_against = points.get("against", {})
        result = {
            "points_per_game": float(pts_for.get("average", {}).get("all", 75.0) or 75.0),
            "points_allowed_per_game": float(pts_against.get("average", {}).get("all", 75.0) or 75.0),
            "home_points_per_game": float(pts_for.get("average", {}).get("home", 78.0) or 78.0),
            "away_points_per_game": float(pts_for.get("average", {}).get("away", 72.0) or 72.0),
            "home_allowed_per_game": float(pts_against.get("average", {}).get("home", 73.0) or 73.0),
            "away_allowed_per_game": float(pts_against.get("average", {}).get("away", 77.0) or 77.0),
            "win_pct": round(wins_all / max(games_played, 1), 3),
            "games_played": games_played,
        }
    except Exception as e:
        print(f"Team stats error {team_id}: {e}")
    _cache[cache_key] = result
    return result

def _default_stats():
    return {
        "points_per_game": 75.0,
        "points_allowed_per_game": 75.0,
        "home_points_per_game": 78.0,
        "away_points_per_game": 72.0,
        "home_allowed_per_game": 73.0,
        "away_allowed_per_game": 77.0,
        "win_pct": 0.500,
        "games_played": 0,
    }

def get_odds(api_key):
    if "odds" in _cache:
        return _cache["odds"]
    odds = []
    try:
        url = "https://api.the-odds-api.com/v4/sports/basketball_wnba/odds"
        params = {
            "apiKey": api_key,
            "regions": "us",
            "markets": "totals,spreads",
            "oddsFormat": "american",
            "bookmakers": "draftkings,fanduel,betmgm"
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if isinstance(data, list):
            seen = set()
            for game in data:
                key = f"{game.get('home_team')}_{game.get('away_team')}"
                if key in seen:
                    continue
                seen.add(key)
                entry = {
                    "home_team": game.get("home_team"),
                    "away_team": game.get("away_team"),
                    "total": None,
                    "spread": None,
                }
                for bookmaker in game.get("bookmakers", [])[:1]:
                    for market in bookmaker.get("markets", []):
                        if market["key"] == "totals":
                            for outcome in market["outcomes"]:
                                if outcome["name"] == "Over":
                                    entry["total"] = outcome["point"]
                        if market["key"] == "spreads":
                            for outcome in market["outcomes"]:
                                if outcome["name"] == game["home_team"]:
                                    entry["spread"] = outcome["point"]
                odds.append(entry)
    except Exception as e:
        print(f"Odds error: {e}")
    _cache["odds"] = odds
    return odds

def build_game_context(game):
    league_id = game.get("league_id")
    home_stats = get_team_stats(game.get("home_id"), league_id)
    away_stats = get_team_stats(game.get("away_id"), league_id)
    return {
        "home_stats": home_stats,
        "away_stats": away_stats,
        "league_tier": game.get("league_tier", 2),
        "league_id": league_id,
        "league_name": game.get("league_name"),
    }

def clear_cache():
    global _games_data_cache
    _cache.clear()
    _games_data_cache = []

def preload_all_data(api_key):
    global _games_data_cache
    print("Preloading basketball game data...")
    games = get_todays_games()
    if not games:
        print("No games today")
        return []
    odds_list = get_odds(api_key)
    games_data = []
    for game in games:
        print(f"Loading: {game['away_team']} @ {game['home_team']} ({game['league_name']})")
        context = build_game_context(game)
        odds_entry = next((
            o for o in odds_list
            if game["home_team"].lower()[:8] in (o.get("home_team") or "").lower() or
            game["away_team"].lower()[:8] in (o.get("away_team") or "").lower()
        ), None)
        games_data.append((game, context, odds_entry))
    _games_data_cache = games_data
    print(f"Preloaded {len(games_data)} basketball games")
    return games_data

def get_cached_games_data():
    return _games_data_cache
