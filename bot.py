import logging
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TIMEZONE,
                    ODDS_API_KEY, MIN_CONFIDENCE, MIN_MODELS_AGREE,
                    RL_MIN_CONFIDENCE, EDGE_THRESHOLD)
from data import preload_all_data, get_cached_games_data, clear_cache

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO)
logger = logging.getLogger(__name__)

tz = pytz.timezone(TIMEZONE)
_notified_games = set()

async def send_message(app, text):
    try:
        max_len = 4096
        if len(text) <= max_len:
            await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        else:
            for i in range(0, len(text), max_len):
                await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text[i:i+max_len])
    except Exception as e:
        logger.error(f"Send message error: {e}")

async def fetch_all_games(api_key=None):
    from model import predict_game
    cached = get_cached_games_data()
    if not cached:
        cached = preload_all_data(api_key or ODDS_API_KEY)
    if not cached:
        return [], []
    games_data = []
    for game, context, odds_entry in cached:
        total = odds_entry.get("total") if odds_entry else None
        spread = odds_entry.get("spread") if odds_entry else None
        prediction = predict_game(context, total, spread)
        games_data.append((game, prediction, odds_entry))
    try:
        from sheets import log_prediction
        if not hasattr(fetch_all_games, "_logged"):
            fetch_all_games._logged = set()
        _logged = fetch_all_games._logged
        for game, prediction, odds_entry in games_data:
            if prediction and (prediction.get("edge_flagged") or
                               prediction.get("spread_edge_flagged")):
                game_key = f"{game['away_team']} @ {game['home_team']}"
                if game_key not in _logged:
                    log_prediction(game, prediction, odds_entry)
                    _logged.add(game_key)
    except Exception as e:
        print(f"Prediction logging error: {e}")
    return [g for g, c, o in cached], games_data

def format_summary(games_data, now):
    from data import _cache
    showing_next = _cache.get("showing_next_day", False)
    day_label = "tomorrow" if showing_next else "today"
    edge_count = sum(1 for _, p, _ in games_data
                     if p and (p.get("edge_flagged") or p.get("spread_edge_flagged")))
    total_games = len(games_data)
    msg = f"🏀 Basketball Edge — {now}\n"
    msg += f"{total_games} games {day_label} | {edge_count} edge(s) flagged\n\n"
    if edge_count == 0:
        msg += "No edges flagged — check back later.\n"
        return msg
    msg += "Today's edges:\n\n"
    flagged = [(g, p, o) for g, p, o in games_data
               if p and (p.get("edge_flagged") or p.get("spread_edge_flagged"))]
    flagged.sort(key=lambda x: x[0].get("league_tier", 3))
    current_tier = None
    for game, pred, odds in flagged:
        if not pred:
            continue
        tier = game.get("league_tier", 3)
        if tier != current_tier:
            current_tier = tier
            tier_label = {1: "⭐ Tier 1", 2: "🔸 Tier 2", 3: "🔹 Tier 3"}.get(tier, "")
            msg += f"{'━'*20}\n{tier_label}\n"
        home = game["home_team"]
        away = game["away_team"]
        league = game["league_name"]
        country = game.get("country", "")
        total = odds.get("total") if odds else None
        total_str = str(total) if total else "N/A"
        ou_skip = (pred["total_conf"] < MIN_CONFIDENCE or abs(pred["total_gap"]) < EDGE_THRESHOLD)
        spread_skip = (pred["spread_conf"] < RL_MIN_CONFIDENCE or pred["spread_votes"] < MIN_MODELS_AGREE)
        ou_flag = "⏭" if ou_skip else "✅"
        spread_flag = "⏭" if spread_skip else "✅"
        game_flag = "⚡" if pred.get("has_data", True) else "⚠️"
        msg += f"{game_flag} {away} @ {home} ({league} — {country})\n"
        msg += f"   O/U: {pred['total_pred']} {total_str} ({pred['total_votes']}/4, {pred['total_conf']}%)  {ou_flag}\n"
        msg += f"   Spread: {pred['spread_pred']} ({pred['spread_votes']}/4, {pred['spread_conf']}%)  {spread_flag}\n"
    msg += "\nType /basketball_edge for full details"
    return msg

async def morning_brief(app):
    now = datetime.now(tz).strftime("%b %d, %Y")
    games, games_data = await fetch_all_games(ODDS_API_KEY)
    if not games:
        await send_message(app, f"🏀 Basketball Edge — {now}\n\nNo games today.")
        return
    edge_count = sum(1 for _, p, _ in games_data
                     if p and (p.get("edge_flagged") or p.get("spread_edge_flagged")))
    if edge_count > 0:
        await send_message(app, format_summary(games_data, now))
    else:
        await send_message(app, f"🏀 Basketball Edge — {now}\n\n{len(games_data)} games — no edges flagged.")

async def cmd_basketball_brief(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Loading basketball edges...")
    now = datetime.now(tz).strftime("%b %d, %Y %H:%M SGT")
    games, games_data = await fetch_all_games(ODDS_API_KEY)
    if not games:
        await update.message.reply_text("No games today.")
        return
    await update.message.reply_text(format_summary(games_data, now))

async def cmd_basketball_edge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching edges...")
    now = datetime.now(tz).strftime("%b %d, %Y %H:%M SGT")
    games, games_data = await fetch_all_games(ODDS_API_KEY)
    if not games:
        await update.message.reply_text("No games today.")
        return
    flagged = [(g, p, o) for g, p, o in games_data
               if p and (p.get("edge_flagged") or p.get("spread_edge_flagged"))]
    if not flagged:
        await update.message.reply_text(f"🏀 Basketball Edges — {now}\n\nNo edges flagged today.")
        return
    flagged.sort(key=lambda x: x[0].get("league_tier", 3))
    msg = f"🏀 Basketball Edges — {now}\n{len(flagged)} edge(s)\n{'━'*20}\n\n"
    current_tier = None
    for game, pred, odds in flagged:
        tier = game.get("league_tier", 3)
        if tier != current_tier:
            current_tier = tier
            tier_label = {1: "⭐ Tier 1", 2: "🔸 Tier 2", 3: "🔹 Tier 3"}.get(tier, "")
            msg += f"{'━'*20}\n{tier_label}\n\n"
        total = odds.get("total") if odds else None
        total_str = str(total) if total else "N/A"
        start = game.get("start_time_sgt", "")
        if start:
            try:
                dt = datetime.fromisoformat(start)
                start = dt.strftime("%b %d %I:%M %p SGT")
            except Exception:
                pass
        ou_skip = (pred["total_conf"] < MIN_CONFIDENCE or abs(pred["total_gap"]) < EDGE_THRESHOLD)
        spread_skip = (pred["spread_conf"] < RL_MIN_CONFIDENCE or pred["spread_votes"] < MIN_MODELS_AGREE)
        ou_flag = "⏭" if ou_skip else "✅"
        spread_flag = "⏭" if spread_skip else "✅"
        msg += f"⚡ {game['away_team']} @ {game['home_team']}\n"
        msg += f"🏆 {game['league_name']} — {game['country']}\n"
        if start:
            msg += f"🕐 {start}\n"
        msg += f"Our total: {pred['our_total']} | Open: {total_str} (gap: {pred['total_gap']:+.1f})\n"
        msg += f"O/U: {pred['total_pred']} — {pred['total_conf']}% — {pred['total_votes']}/4  {ou_flag}\n"
        msg += f"Spread: {pred['spread_pred']} — {pred['spread_conf']}% — {pred['spread_votes']}/4  {spread_flag}\n"
        msg += f"Win prob: Home {pred['home_win_prob']*100:.0f}% / Away {pred['away_win_prob']*100:.0f}%\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"
    await update.message.reply_text(msg)

async def cmd_basketball_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Refreshing...")
    clear_cache()
    games, games_data = await fetch_all_games(ODDS_API_KEY)
    edge_count = sum(1 for _, p, _ in games_data
                     if p and (p.get("edge_flagged") or p.get("spread_edge_flagged")))
    await update.message.reply_text(f"✅ Refreshed — {len(games_data)} games, {edge_count} edge(s)")

async def cmd_basketball_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching results...")
    try:
        from sheets import log_results, update_results_in_sheet, get_results_date
        results_date = get_results_date()
        results = log_results()
        if not results:
            await update.message.reply_text("No final results yet.")
            return
        _, games_data = await fetch_all_games(ODDS_API_KEY)
        update_results_in_sheet(results, games_data)
        msg = f"🏀 Results — {results_date}\n━━━━━━━━━━━━━━━━━━━━\n"
        for r in results[:15]:
            msg += f"• {r['game']} — {r['away_score']}-{r['home_score']} (total: {r['total_result']})\n"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def cmd_basketball_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching record...")
    try:
        from sheets import get_record
        record = get_record()
        if not record or record.get("total", 0) == 0:
            await update.message.reply_text(
                "No results logged yet.\nRun /basketball_results after games finish.")
            return
        msg = "📊 Basketball Edge Record\n━━━━━━━━━━━━━━━━━━━━\n"
        msg += "\n🎯 Flagged bets (actionable):\n"
        msg += f"  Spread: {record['spread_flagged_correct']}/{record['spread_flagged_total']} ({record['spread_flagged_accuracy']}%)\n"
        msg += f"  O/U: {record['ou_flagged_correct']}/{record['ou_flagged_total']} ({record['ou_flagged_accuracy']}%)\n"
        msg += "\n📊 All games (model validation):\n"
        msg += f"  Spread: {record['spread_correct']}/{record['spread_total']} ({record['spread_accuracy']}%)\n"
        msg += f"  O/U: {record['ou_correct']}/{record['ou_total']} ({record['ou_accuracy']}%)\n"
        if record.get("monthly"):
            msg += "\nMonthly (flagged Spread):\n"
            for month, data in sorted(record["monthly"].items(), reverse=True)[:6]:
                s = data.get("spread", 0)
                sc = data.get("spread_correct", 0)
                acc = round(sc / s * 100, 1) if s > 0 else 0
                msg += f"  {month}: {sc}/{s} ({acc}%)\n"
            msg += "\nMonthly (flagged O/U):\n"
            for month, data in sorted(record["monthly"].items(), reverse=True)[:6]:
                o = data.get("ou", 0)
                oc = data.get("ou_correct", 0)
                acc = round(oc / o * 100, 1) if o > 0 else 0
                msg += f"  {month}: {oc}/{o} ({acc}%)\n"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def cmd_basketball_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(tz).strftime("%b %d %Y %H:%M SGT")
    cached = get_cached_games_data()
    msg = (f"🏀 Basketball Edge Bot\n\n"
           f"🕐 {now}\n"
           f"📊 Games loaded: {len(cached)}\n"
           f"✅ Bot is live\n\n"
           f"Commands:\n"
           f"/basketball_brief — today's edges\n"
           f"/basketball_edge — full edge details\n"
           f"/basketball_refresh — refresh data\n"
           f"/basketball_results — log results\n"
           f"/basketball_record — win/loss record")
    await update.message.reply_text(msg)

def main():
    print("Starting Basketball Edge Bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("basketball_brief", cmd_basketball_brief))
    app.add_handler(CommandHandler("basketball_edge", cmd_basketball_edge))
    app.add_handler(CommandHandler("basketball_refresh", cmd_basketball_refresh))
    app.add_handler(CommandHandler("basketball_results", cmd_basketball_results))
    app.add_handler(CommandHandler("basketball_record", cmd_basketball_record))
    app.add_handler(CommandHandler("basketball_status", cmd_basketball_status))
    from scheduler import setup_scheduler
    scheduler = setup_scheduler(app)

    async def post_init(application):
        scheduler.start()
        print("Scheduler started — SGT timezone")
        import threading
        t = threading.Thread(target=preload_all_data, args=(ODDS_API_KEY,), daemon=True)
        t.start()
        print("Basketball Edge Bot is live — preloading in background")

    app.post_init = post_init
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
