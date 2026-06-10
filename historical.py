import requests
import numpy as np
import pickle
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")
from config import API_BASKETBALL_BASE, API_HEADERS, LEAGUE_TIERS, TIER_FACTORS, LEAGUE_AVG_TOTALS, DEFAULT_AVG_TOTAL

SEASON_WEIGHTS = {2023: 0.5, 2024: 0.75, 2025: 1.0, 2026: 2.0}

def get_league_avg(league_id):
   return LEAGUE_AVG_TOTALS.get(league_id, DEFAULT_AVG_TOTAL)

def get_season_games(league_id, season):
   print(f"  Fetching league {league_id} season {season}...", flush=True)
   games = []
   try:
       url = f"{API_BASKETBALL_BASE}/games"
       params = {"league": league_id, "season": season}
       r = requests.get(url, headers=API_HEADERS, params=params, timeout=30)
       if r.status_code != 200:
           return games
       for game in r.json().get("response", []):
           status = game.get("status", {}).get("long", "")
           if status not in ["Finished", "FT"]:
               continue
           home = game.get("teams", {}).get("home", {})
           away = game.get("teams", {}).get("away", {})
           scores = game.get("scores", {})
           home_score = scores.get("home", {}).get("total")
           away_score = scores.get("away", {}).get("total")
           if home_score is None or away_score is None:
               continue
           date_str = game.get("date", "")[:10]
           month = int(date_str[5:7]) if len(date_str) >= 7 else 6
           games.append({
               "game_id": game.get("id"),
               "date": date_str, "season": season, "month": month,
               "league_id": league_id,
               "home_id": home.get("id"), "away_id": away.get("id"),
               "home_team": home.get("name", ""),
               "away_team": away.get("name", ""),
               "home_score": int(home_score), "away_score": int(away_score),
               "total": int(home_score) + int(away_score),
           })
   except Exception as e:
       print(f"  Error league {league_id} season {season}: {e}")
   return games

def get_team_stats(team_id, league_id, season):
   if not team_id:
       return None
   try:
       url = f"{API_BASKETBALL_BASE}/teams/statistics"
       params = {"league": league_id, "season": season, "team": team_id}
       r = requests.get(url, headers=API_HEADERS, params=params, timeout=10)
       if r.status_code != 200:
           return None
       data = r.json().get("response", {})
       if not data:
           return None
       games = data.get("games", {})
       points = data.get("points", {})
       wins = int(games.get("wins", {}).get("all", 0) or 0)
       played = int(games.get("played", {}).get("all", 1) or 1)
       pts_for = points.get("for", {})
       pts_against = points.get("against", {})
       return {
           "points_per_game": float(pts_for.get("average", {}).get("all", 75.0) or 75.0),
           "points_allowed_per_game": float(pts_against.get("average", {}).get("all", 75.0) or 75.0),
           "home_points_per_game": float(pts_for.get("average", {}).get("home", 78.0) or 78.0),
           "away_points_per_game": float(pts_for.get("average", {}).get("away", 72.0) or 72.0),
           "home_allowed_per_game": float(pts_against.get("average", {}).get("home", 73.0) or 73.0),
           "away_allowed_per_game": float(pts_against.get("average", {}).get("away", 77.0) or 77.0),
           "win_pct": round(wins / max(played, 1), 3),
           "games_played": played,
       }
   except Exception:
       return None

def default_stats():
   return {
       "points_per_game": 75.0, "points_allowed_per_game": 75.0,
       "home_points_per_game": 78.0, "away_points_per_game": 72.0,
       "home_allowed_per_game": 73.0, "away_allowed_per_game": 77.0,
       "win_pct": 0.500, "games_played": 0,
   }

def build_features(home_stats, away_stats, league_id, tier, total):
   hs = home_stats or default_stats()
   as_ = away_stats or default_stats()
   tier_factor = TIER_FACTORS.get(tier, 0.70)
   league_avg = get_league_avg(league_id)
   home_ppg = max(50.0, min(float(hs.get("points_per_game", 75.0)), 120.0))
   away_ppg = max(50.0, min(float(as_.get("points_per_game", 75.0)), 120.0))
   home_apg = max(50.0, min(float(hs.get("points_allowed_per_game", 75.0)), 120.0))
   away_apg = max(50.0, min(float(as_.get("points_allowed_per_game", 75.0)), 120.0))
   home_home_ppg = max(50.0, min(float(hs.get("home_points_per_game", 78.0)), 120.0))
   away_away_ppg = max(50.0, min(float(as_.get("away_points_per_game", 72.0)), 120.0))
   home_home_apg = max(50.0, min(float(hs.get("home_allowed_per_game", 73.0)), 120.0))
   away_away_apg = max(50.0, min(float(as_.get("away_allowed_per_game", 77.0)), 120.0))
   home_win = float(hs.get("win_pct", 0.500))
   away_win = float(as_.get("win_pct", 0.500))
   implied_total = (home_home_ppg + away_away_ppg + away_away_apg + home_home_apg) / 2
   implied_total = max(100.0, min(implied_total, 220.0))
   vegas_line = total if total else league_avg
   total_gap = (implied_total - vegas_line) / 4
   home_str = (home_ppg - home_apg + (home_win - 0.5) * 10)
   away_str = (away_ppg - away_apg + (away_win - 0.5) * 10)
   str_diff = home_str - away_str
   spread_norm = (-3.5 if str_diff > 0 else 3.5) / 10
   month = 6
   fatigue = (1.0 if month <= 3 else 1.03 if month <= 6 else 1.05 if month <= 9 else 1.0)
   return [
       home_ppg, away_ppg, home_apg, away_apg,
       home_home_ppg, away_away_ppg, home_home_apg, away_away_apg,
       home_win, away_win, implied_total, total_gap,
       (home_ppg + away_ppg - 150.0) / 20,
       (home_apg + away_apg - 150.0) / 20,
       home_home_ppg - home_ppg, away_away_ppg - away_ppg,
       home_win - away_win, str_diff, spread_norm,
       (vegas_line - league_avg) / 10, tier_factor, fatigue,
   ]

def train_on_historical():
   from sklearn.linear_model import LogisticRegression
   from sklearn.neural_network import MLPClassifier
   from sklearn.ensemble import RandomForestClassifier
   from sklearn.preprocessing import StandardScaler
   from sklearn.model_selection import train_test_split
   from sklearn.metrics import accuracy_score
   from sklearn.utils.class_weight import compute_class_weight
   from xgboost import XGBClassifier

   print("Building basketball historical dataset...")
   print("Leagues: WNBA + international women's | Seasons: 2023-2026\n")

   X, y_total, y_spread, weights = [], [], [], []
   team_cache = {}
   total_games = total_skipped = 0

   for league_id, league_info in LEAGUE_TIERS.items():
       tier = league_info["tier"]
       league_avg = get_league_avg(league_id)
       league_games = 0
       for season in [2023, 2024, 2025, 2026]:
           season_weight = SEASON_WEIGHTS.get(season, 1.0)
           games = get_season_games(league_id, season)
           if not games:
               continue
           print(f"  Processing {league_info['name']} {season} — {len(games)} games (weight: {season_weight}x)...", flush=True)
           for game in games:
               try:
                   home_id = game["home_id"]
                   away_id = game["away_id"]
                   ht_key = f"{home_id}_{league_id}_{season}"
                   at_key = f"{away_id}_{league_id}_{season}"
                   if ht_key not in team_cache:
                       team_cache[ht_key] = get_team_stats(home_id, league_id, season)
                   if at_key not in team_cache:
                       team_cache[at_key] = get_team_stats(away_id, league_id, season)
                   features = build_features(
                       team_cache[ht_key], team_cache[at_key],
                       league_id, tier, league_avg)
                   actual_total = game["total"]
                   goes_over = 1 if actual_total > league_avg else 0
                   home_wins_spread = 1 if (game["home_score"] - game["away_score"]) > 3.5 else 0
                   X.append(features)
                   y_total.append(goes_over)
                   y_spread.append(home_wins_spread)
                   weights.append(season_weight)
                   total_games += 1
                   league_games += 1
               except Exception:
                   total_skipped += 1
                   continue
       print(f"  {league_info['name']}: {league_games} games processed", flush=True)

   print(f"\nTotal dataset: {total_games} games, {total_skipped} skipped")
   if len(X) < 100:
       print("Not enough data — using simulated training")
       from model import train_models
       train_models()
       return False

   X = np.array(X)
   y_total = np.array(y_total)
   y_spread = np.array(y_spread)
   sample_weights = np.array(weights)

   print(f"\nTraining on {len(X)} real games...")
   scaler = StandardScaler()
   X_scaled = scaler.fit_transform(X)
   X_train, X_test, yt_train, yt_test, sw_train, _ = train_test_split(
       X_scaled, y_total, sample_weights, test_size=0.2, random_state=42)
   _, _, ys_train, ys_test, _, _ = train_test_split(
       X_scaled, y_spread, sample_weights, test_size=0.2, random_state=42)

   total_cw = dict(zip(np.unique(yt_train),
       compute_class_weight("balanced", classes=np.unique(yt_train), y=yt_train)))
   spread_cw = dict(zip(np.unique(ys_train),
       compute_class_weight("balanced", classes=np.unique(ys_train), y=ys_train)))

   models_total = {}
   models_spread = {}

   print("Training Logistic Regression...")
   lr_t = LogisticRegression(max_iter=2000, C=0.5, class_weight=total_cw, random_state=42)
   lr_t.fit(X_train, yt_train, sample_weight=sw_train)
   models_total["lr"] = lr_t
   print(f"  LR Total: {accuracy_score(yt_test, lr_t.predict(X_test)):.3f}")
   lr_s = LogisticRegression(max_iter=2000, C=0.5, class_weight=spread_cw, random_state=42)
   lr_s.fit(X_train, ys_train, sample_weight=sw_train)
   models_spread["lr"] = lr_s
   print(f"  LR Spread: {accuracy_score(ys_test, lr_s.predict(X_test)):.3f}")

   print("Training Random Forest...")
   rf_t = RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=20, class_weight=total_cw, random_state=42)
   rf_t.fit(X_train, yt_train, sample_weight=sw_train)
   models_total["rf"] = rf_t
   print(f"  RF Total: {accuracy_score(yt_test, rf_t.predict(X_test)):.3f}")
   rf_s = RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=20, class_weight=spread_cw, random_state=42)
   rf_s.fit(X_train, ys_train, sample_weight=sw_train)
   models_spread["rf"] = rf_s
   print(f"  RF Spread: {accuracy_score(ys_test, rf_s.predict(X_test)):.3f}")

   print("Training XGBoost...")
   sps_t = sum(yt_train == 0) / max(sum(yt_train == 1), 1)
   xgb_t = XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, scale_pos_weight=sps_t, random_state=42, eval_metric="logloss", verbosity=0)
   xgb_t.fit(X_train, yt_train, sample_weight=sw_train)
   models_total["xgb"] = xgb_t
   print(f"  XGB Total: {accuracy_score(yt_test, xgb_t.predict(X_test)):.3f}")
   sps_s = sum(ys_train == 0) / max(sum(ys_train == 1), 1)
   xgb_s = XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, scale_pos_weight=sps_s, random_state=42, eval_metric="logloss", verbosity=0)
   xgb_s.fit(X_train, ys_train, sample_weight=sw_train)
   models_spread["xgb"] = xgb_s
   print(f"  XGB Spread: {accuracy_score(ys_test, xgb_s.predict(X_test)):.3f}")

   print("Training Neural Network...")
   nn_t = MLPClassifier(hidden_layer_sizes=(64, 32, 16), max_iter=3000, learning_rate_init=0.001, early_stopping=True, validation_fraction=0.1, random_state=42)
   nn_t.fit(X_train, yt_train)
   models_total["nn"] = nn_t
   print(f"  NN Total: {accuracy_score(yt_test, nn_t.predict(X_test)):.3f}")
   nn_s = MLPClassifier(hidden_layer_sizes=(64, 32, 16), max_iter=3000, learning_rate_init=0.001, early_stopping=True, validation_fraction=0.1, random_state=42)
   nn_s.fit(X_train, ys_train)
   models_spread["nn"] = nn_s
   print(f"  NN Spread: {accuracy_score(ys_test, nn_s.predict(X_test)):.3f}")

   with open("models.pkl", "wb") as f:
       pickle.dump({
           "models_total": models_total, "models_spread": models_spread,
           "scaler": scaler, "trained_on": "basketball_all_leagues_2023_2026",
           "games_count": len(X),
       }, f)

   print(f"\n✅ Training complete — {len(X)} real games")
   print("models.pkl saved")
   return True

if __name__ == "__main__":
   train_on_historical()
