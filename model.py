import numpy as np
import pickle
import os
from datetime import datetime
import pytz

TIER_FACTORS = {1: 1.0, 2: 0.85, 3: 0.70}

def get_league_avg(league_id):
   from config import LEAGUE_AVG_TOTALS, DEFAULT_AVG_TOTAL
   return LEAGUE_AVG_TOTALS.get(league_id, DEFAULT_AVG_TOTAL)

def build_features(context, total, spread):
   try:
       hs = context.get("home_stats") or {}
       as_ = context.get("away_stats") or {}
       tier = context.get("league_tier", 2)
       league_id = context.get("league_id", 0)
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
       spread_norm = (spread or (-3.5 if str_diff > 0 else 3.5)) / 10
       ppg_sum = (home_ppg + away_ppg - 150.0) / 20
       apg_sum = (home_apg + away_apg - 150.0) / 20
       home_split = home_home_ppg - home_ppg
       away_split = away_away_ppg - away_ppg
       win_diff = home_win - away_win
       total_norm = (vegas_line - league_avg) / 10
       current_month = datetime.now(pytz.timezone("Asia/Singapore")).month
       fatigue = (1.0 if current_month <= 3 else 1.03 if current_month <= 6 else 1.05 if current_month <= 9 else 1.0)
       return [
           home_ppg, away_ppg, home_apg, away_apg,
           home_home_ppg, away_away_ppg, home_home_apg, away_away_apg,
           home_win, away_win, implied_total, total_gap,
           ppg_sum, apg_sum, home_split, away_split,
           win_diff, str_diff, spread_norm, total_norm,
           tier_factor, fatigue,
       ]
   except Exception as e:
       print(f"Feature error: {e}")
       return None

def train_models():
   from sklearn.linear_model import LogisticRegression
   from sklearn.neural_network import MLPClassifier
   from sklearn.ensemble import RandomForestClassifier
   from sklearn.preprocessing import StandardScaler
   from sklearn.model_selection import train_test_split
   from xgboost import XGBClassifier
   print("Generating simulated basketball training data...")
   np.random.seed(42)
   X, y_total, y_spread = [], [], []
   for _ in range(1500):
       home_ppg = np.random.normal(75.0, 8.0)
       away_ppg = np.random.normal(75.0, 8.0)
       home_apg = np.random.normal(75.0, 8.0)
       away_apg = np.random.normal(75.0, 8.0)
       home_home_ppg = home_ppg * np.random.uniform(1.0, 1.08)
       away_away_ppg = away_ppg * np.random.uniform(0.92, 1.0)
       home_home_apg = home_apg * np.random.uniform(0.92, 1.0)
       away_away_apg = away_apg * np.random.uniform(1.0, 1.08)
       home_win = np.random.uniform(0.25, 0.75)
       away_win = np.random.uniform(0.25, 0.75)
       tier = np.random.choice([1, 2, 3])
       tier_factor = TIER_FACTORS.get(tier, 0.70)
       league_avg = np.random.choice([148.0, 150.0, 152.0, 155.0, 160.0])
       total = league_avg + np.random.uniform(-8.0, 8.0)
       h_ppg = max(50.0, min(home_ppg, 120.0))
       a_ppg = max(50.0, min(away_ppg, 120.0))
       h_apg = max(50.0, min(home_apg, 120.0))
       a_apg = max(50.0, min(away_apg, 120.0))
       h_home = max(50.0, min(home_home_ppg, 120.0))
       a_away = max(50.0, min(away_away_ppg, 120.0))
       h_home_a = max(50.0, min(home_home_apg, 120.0))
       a_away_a = max(50.0, min(away_away_apg, 120.0))
       implied = (h_home + a_away + a_away_a + h_home_a) / 2
       implied = max(100.0, min(implied, 220.0))
       total_gap = (implied - total) / 4
       home_str = (h_ppg - h_apg + (home_win - 0.5) * 10)
       away_str = (a_ppg - a_apg + (away_win - 0.5) * 10)
       str_diff = home_str - away_str
       spread_norm = (-3.5 if str_diff > 0 else 3.5) / 10
       features = [
           h_ppg, a_ppg, h_apg, a_apg,
           h_home, a_away, h_home_a, a_away_a,
           home_win, away_win, implied, total_gap,
           (h_ppg + a_ppg - 150.0) / 20,
           (h_apg + a_apg - 150.0) / 20,
           h_home - h_ppg, a_away - a_ppg,
           home_win - away_win, str_diff,
           spread_norm, (total - league_avg) / 10,
           tier_factor, 1.0,
       ]
       noise = np.random.normal(0, 8.0)
       actual = implied + noise
       goes_over = 1 if actual > total else 0
       margin = str_diff * 0.8 + np.random.normal(0, 6.0)
       home_covers = 1 if margin > 3.5 else 0
       X.append(features)
       y_total.append(goes_over)
       y_spread.append(home_covers)
   X = np.array(X)
   scaler = StandardScaler()
   X_scaled = scaler.fit_transform(X)
   X_train, X_test, yt_train, yt_test = train_test_split(X_scaled, y_total, test_size=0.2, random_state=42)
   _, _, ys_train, ys_test = train_test_split(X_scaled, y_spread, test_size=0.2, random_state=42)
   models_total = {}
   models_spread = {}
   for name, ct, cs in [
       ("lr", LogisticRegression(max_iter=1000, random_state=42), LogisticRegression(max_iter=1000, random_state=42)),
       ("rf", RandomForestClassifier(n_estimators=100, random_state=42), RandomForestClassifier(n_estimators=100, random_state=42)),
       ("xgb", XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42, eval_metric="logloss", verbosity=0), XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42, eval_metric="logloss", verbosity=0)),
       ("nn", MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=2000, random_state=42), MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=2000, random_state=42)),
   ]:
       ct.fit(X_train, yt_train)
       models_total[name] = ct
       cs.fit(X_train, ys_train)
       models_spread[name] = cs
   with open("models.pkl", "wb") as f:
       pickle.dump({"models_total": models_total, "models_spread": models_spread, "scaler": scaler}, f)
   print("Simulated basketball models saved.")
   return models_total, models_spread, scaler

def load_models():
   if os.path.exists("models.pkl"):
       with open("models.pkl", "rb") as f:
           data = pickle.load(f)
       if "models_spread" in data:
           return data["models_total"], data["models_spread"], data["scaler"]
   return None, None, None

def ensemble_predict(models, X_scaled):
   weights = {"lr": 1, "rf": 2, "xgb": 3, "nn": 2}
   weighted_prob = total_weight = 0
   yes_votes = no_votes = 0
   for name, model in models.items():
       prob = model.predict_proba(X_scaled)[0][1]
       w = weights.get(name, 1)
       weighted_prob += prob * w
       total_weight += w
       if prob > 0.5:
           yes_votes += 1
       else:
           no_votes += 1
   return weighted_prob / total_weight, yes_votes, no_votes, len(models)

def monte_carlo_simulate(context, total, n=10000):
   np.random.seed(None)
   hs = context.get("home_stats") or {}
   as_ = context.get("away_stats") or {}
   league_id = context.get("league_id", 0)
   league_avg = get_league_avg(league_id)
   home_exp = max(50.0, float(hs.get("home_points_per_game", 78.0)))
   away_exp = max(50.0, float(as_.get("away_points_per_game", 72.0)))
   home_def = max(50.0, float(hs.get("home_allowed_per_game", 73.0)))
   away_def = max(50.0, float(as_.get("away_allowed_per_game", 77.0)))
   home_score_exp = (home_exp + away_def) / 2
   away_score_exp = (away_exp + home_def) / 2
   home_scores = np.random.normal(home_score_exp, 8.0, n)
   away_scores = np.random.normal(away_score_exp, 8.0, n)
   totals = home_scores + away_scores
   vegas = total if total else league_avg
   home_wins = np.sum(home_scores > away_scores)
   return {
       "home_win_prob": round(home_wins / n, 3),
       "away_win_prob": round(1 - home_wins / n, 3),
       "over_prob": round(np.sum(totals > vegas) / n, 3),
       "simulated_avg_total": round(float(np.mean(totals)), 1),
   }

def predict_game(context, total, spread):
   models_total, models_spread, scaler = load_models()
   if models_total is None:
       train_models()
       models_total, models_spread, scaler = load_models()
   features = build_features(context, total, spread)
   if features is None:
       return None
   f = np.array(features).reshape(1, -1)
   try:
       f_scaled = scaler.transform(f)
   except Exception:
       train_models()
       models_total, models_spread, scaler = load_models()
       f_scaled = scaler.transform(f)
   total_prob, total_yes, total_no, total_count = ensemble_predict(models_total, f_scaled)
   spread_prob, spread_yes, spread_no, spread_count = ensemble_predict(models_spread, f_scaled)
   mc = monte_carlo_simulate(context, total)
   hs = context.get("home_stats") or {}
   as_ = context.get("away_stats") or {}
   league_id = context.get("league_id", 0)
   league_avg = get_league_avg(league_id)
   home_home_ppg = float(hs.get("home_points_per_game", 78.0))
   away_away_ppg = float(as_.get("away_points_per_game", 72.0))
   home_home_apg = float(hs.get("home_allowed_per_game", 73.0))
   away_away_apg = float(as_.get("away_allowed_per_game", 77.0))
   implied_total = (home_home_ppg + away_away_ppg + away_away_apg + home_home_apg) / 2
   implied_total = max(100.0, min(implied_total, 220.0))
   our_total = round(implied_total, 1)
   vegas_line = total if total else league_avg
   total_gap = round(our_total - vegas_line, 1)
   if total_gap > 0:
       total_pred = "OVER"
       total_votes = total_yes
       total_conf = round(total_prob * 100, 1)
   else:
       total_pred = "UNDER"
       total_votes = total_no
       total_conf = round((1 - total_prob) * 100, 1)
   home_str = ((float(hs.get("points_per_game", 75.0)) - float(hs.get("points_allowed_per_game", 75.0))) + (float(hs.get("win_pct", 0.5)) - 0.5) * 10)
   away_str = ((float(as_.get("points_per_game", 75.0)) - float(as_.get("points_allowed_per_game", 75.0))) + (float(as_.get("win_pct", 0.5)) - 0.5) * 10)
   str_diff = home_str - away_str
   home_is_fav = (spread or (-3.5 if str_diff > 0 else 3.5)) < 0
   if spread_prob > 0.5:
       spread_pred = "HOME -3.5" if home_is_fav else "HOME +3.5"
       spread_votes = spread_yes
   else:
       spread_pred = "AWAY +3.5" if home_is_fav else "AWAY -3.5"
       spread_votes = spread_no
   spread_conf = round(max(spread_prob, 1 - spread_prob) * 100, 1)
   home_win_prob = round(mc["home_win_prob"] * 0.6 + spread_prob * 0.4, 3)
   from config import MIN_MODELS_AGREE, MIN_CONFIDENCE, RL_MIN_CONFIDENCE, EDGE_THRESHOLD
   edge_flagged = (abs(total_gap) >= EDGE_THRESHOLD and total_votes >= MIN_MODELS_AGREE and total_conf >= MIN_CONFIDENCE)
   spread_edge_flagged = (spread_votes >= MIN_MODELS_AGREE and spread_conf >= RL_MIN_CONFIDENCE)
   return {
       "our_total": our_total, "total_gap": total_gap,
       "total_pred": total_pred, "total_conf": total_conf,
       "total_votes": total_votes, "total_models": total_count,
       "spread_pred": spread_pred, "spread_conf": spread_conf,
       "spread_votes": spread_votes, "spread_models": spread_count,
       "home_win_prob": home_win_prob, "away_win_prob": round(1 - home_win_prob, 3),
       "mc_avg_total": mc["simulated_avg_total"], "mc_over_prob": mc["over_prob"],
       "edge_flagged": edge_flagged, "spread_edge_flagged": spread_edge_flagged,
       "league_avg": league_avg, "has_data": hs.get("games_played", 0) > 5,
   }
