import requests
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv
load_dotenv()

SHEETS_URL = os.getenv("SHEETS_URL", "")
SHEETS_SECRET = os.getenv("SHEETS_SECRET", "")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Singapore")
tz = pytz.timezone(TIMEZONE)

def log_prediction(game, prediction, odds_entry):
    if not SHEETS_URL or not prediction:
        return
    try:
        today = datetime.now(tz).strftime("%Y-%m-%d")
        game_str = f"{game['away_team']} @ {game['home_team']}"
        total = odds_entry.get("total") if odds_entry else None
        row = [
            today, game_str,
            prediction.get("our_total"), total,
            prediction.get("total_gap"),
            prediction.get("total_pred"),
            prediction.get("total_conf"),
            prediction.get("total_votes"),
            prediction.get("spread_pred"),
            prediction.get("spread_conf"),
            prediction.get("spread_votes"),
            prediction.get("spread_edge_flagged"),
            prediction.get("has_data"),
            None, None, None, None, None, None, None
        ]
        requests.post(SHEETS_URL, json={
            "secret": SHEETS_SECRET,
            "action": "log_prediction",
            "sheet": "basketball_predictions",
            "row": row
        }, timeout=30)
    except Exception as e:
        print(f"Error logging prediction: {e}")

def get_results_date():
    tz_now = datetime.now(tz)
    today = tz_now.strftime("%Y-%m-%d")
    yesterday = (tz_now - timedelta(days=1)).strftime("%Y-%m-%d")
    if tz_now.hour < 11:
        return yesterday
    try:
        from config import API_BASKETBALL_BASE, API_HEADERS, LEAGUE_TIERS
        finals = 0
        for league_id in list(LEAGUE_TIERS.keys())[:5]:
            r = requests.get(f"{API_BASKETBALL_BASE}/games",
                headers=API_HEADERS,
                params={"league": league_id, "date": today},
                timeout=5)
            for g in r.json().get("response", []):
                if g.get("status", {}).get("long") in ["Finished", "FT"]:
                    finals += 1
        return today if finals > 0 else yesterday
    except Exception:
        return yesterday

def log_results(date=None):
    if not SHEETS_URL:
        return []
    try:
        from config import API_BASKETBALL_BASE, API_HEADERS, LEAGUE_TIERS
        tz_now = datetime.now(tz)
        target_date = date or get_results_date()
        results = []
        for league_id in LEAGUE_TIERS.keys():
            r = requests.get(f"{API_BASKETBALL_BASE}/games",
                headers=API_HEADERS,
                params={"league": league_id, "season": tz_now.year, "date": target_date},
                timeout=10)
            for game in r.json().get("response", []):
                if game.get("status", {}).get("long") not in ["Finished", "FT"]:
                    continue
                home = game["teams"]["home"]["name"]
                away = game["teams"]["away"]["name"]
                scores = game.get("scores", {})
                home_score = scores.get("home", {}).get("total")
                away_score = scores.get("away", {}).get("total")
                if home_score is None or away_score is None:
                    continue
                results.append({
                    "game": f"{away} @ {home}",
                    "home_score": int(home_score),
                    "away_score": int(away_score),
                    "total_result": int(home_score) + int(away_score),
                    "date": target_date,
                })
        return results
    except Exception as e:
        print(f"Error fetching results: {e}")
        return []

def update_results_in_sheet(results, predictions_data=None, date_override=None):
    if not SHEETS_URL:
        return
    results_date = date_override or get_results_date()
    try:
        r = requests.get(SHEETS_URL,
            params={"sheet": "basketball_predictions"}, timeout=30)
        data = r.json()
        rows = data.get("rows", []) if isinstance(data, dict) else data
        stored_preds = {}
        for row in rows[1:]:
            if len(row) < 12:
                continue
            try:
                game = str(row[1])
                stored_preds[game] = {
                    "total_pred": str(row[5]),
                    "total_conf": float(row[6] or 0),
                    "spread_pred": str(row[8]),
                    "spread_conf": float(row[9] or 0),
                    "spread_votes": int(row[10] or 0),
                    "edge_flagged": bool(row[11]),
                    "spread_edge_flagged": (float(row[9] or 0) >= 65.0 and int(row[10] or 0) >= 3),
                    "open_total": float(row[3]) if row[3] else None,
                    "league_avg": 150.0,
                }
            except Exception:
                continue
    except Exception as e:
        print(f"Error reading predictions: {e}")
        stored_preds = {}

    for result in results:
        pred = next((p for k, p in stored_preds.items()
                     if result["game"] in k or k in result["game"]), None)
        if not pred:
            continue
        if not (pred.get("edge_flagged") or pred.get("spread_edge_flagged")):
            continue
        home_score = result["home_score"]
        away_score = result["away_score"]
        total_result = result["total_result"]
        open_total = pred.get("open_total") or pred.get("league_avg", 150.0)
        ou_result = "OVER" if total_result > open_total else "UNDER"
        ou_correct = "✅" if pred.get("total_pred") == ou_result else "❌"
        spread_pred = pred.get("spread_pred", "")
        home_margin = home_score - away_score
        if spread_pred == "HOME -3.5":
            spread_correct = "✅" if home_margin > 3.5 else "❌"
        elif spread_pred == "HOME +3.5":
            spread_correct = "✅" if home_margin >= -3.5 else "❌"
        elif spread_pred == "AWAY +3.5":
            spread_correct = "✅" if home_margin <= 3.5 else "❌"
        else:
            spread_correct = "✅" if home_margin < -3.5 else "❌"
        try:
            r = requests.post(SHEETS_URL, json={
                "secret": SHEETS_SECRET,
                "action": "log_result",
                "sheet": "basketball_predictions",
                "date": results_date,
                "game": result["game"],
                "home_score": home_score,
                "away_score": away_score,
                "total_result": total_result,
                "ou_result": ou_result,
                "ou_correct": ou_correct,
                "rl_result": spread_pred,
                "rl_correct": spread_correct,
                "correct": spread_correct
            }, timeout=30)
            print(f"Result: {result['game']} | Spread: {spread_pred} {spread_correct} | O/U: {ou_result} {ou_correct}")
        except Exception as e:
            print(f"Error updating result: {e}")

def get_record():
    if not SHEETS_URL:
        return None
    try:
        r = requests.get(SHEETS_URL,
            params={"sheet": "basketball_predictions"}, timeout=30)
        data = r.json()
        rows = data.get("rows", []) if isinstance(data, dict) else data
        if len(rows) <= 1:
            return None
        spread_total = spread_correct_count = 0
        ou_total = ou_correct_count = 0
        spread_flagged_total = spread_flagged_correct = 0
        ou_flagged_total = ou_flagged_correct = 0
        monthly = {}
        for row in rows[1:]:
            if len(row) < 19:
                continue
            date = str(row[0])[:7]
            spread_corr = str(row[19]) if len(row) > 19 else ""
            ou_corr = str(row[17]) if len(row) > 17 else ""
            is_spread_flagged = (float(row[9] or 0) >= 65.0 and int(row[10] or 0) >= 3)
            is_ou_flagged = (str(row[11]) == "True" or row[11] is True)
            if spread_corr in ["✅", "❌"]:
                spread_total += 1
                if spread_corr == "✅":
                    spread_correct_count += 1
                if is_spread_flagged:
                    spread_flagged_total += 1
                    if spread_corr == "✅":
                        spread_flagged_correct += 1
            if ou_corr in ["✅", "❌"]:
                ou_total += 1
                if ou_corr == "✅":
                    ou_correct_count += 1
                if is_ou_flagged:
                    ou_flagged_total += 1
                    if ou_corr == "✅":
                        ou_flagged_correct += 1
            if date not in monthly:
                monthly[date] = {"spread": 0, "spread_correct": 0, "ou": 0, "ou_correct": 0}
            if spread_corr in ["✅", "❌"] and is_spread_flagged:
                monthly[date]["spread"] += 1
                if spread_corr == "✅":
                    monthly[date]["spread_correct"] += 1
            if ou_corr in ["✅", "❌"] and is_ou_flagged:
                monthly[date]["ou"] += 1
                if ou_corr == "✅":
                    monthly[date]["ou_correct"] += 1
        return {
            "spread_total": spread_total,
            "spread_correct": spread_correct_count,
            "spread_accuracy": round(spread_correct_count / spread_total * 100, 1) if spread_total > 0 else 0,
            "ou_total": ou_total,
            "ou_correct": ou_correct_count,
            "ou_accuracy": round(ou_correct_count / ou_total * 100, 1) if ou_total > 0 else 0,
            "spread_flagged_total": spread_flagged_total,
            "spread_flagged_correct": spread_flagged_correct,
            "spread_flagged_accuracy": round(spread_flagged_correct / spread_flagged_total * 100, 1) if spread_flagged_total > 0 else 0,
            "ou_flagged_total": ou_flagged_total,
            "ou_flagged_correct": ou_flagged_correct,
            "ou_flagged_accuracy": round(ou_flagged_correct / ou_flagged_total * 100, 1) if ou_flagged_total > 0 else 0,
            "total": spread_total + ou_total,
            "monthly": monthly
        }
    except Exception as e:
        print(f"Error getting record: {e}")
        return None
