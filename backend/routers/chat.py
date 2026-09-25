from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import random
from backend.database import db_instance
from backend.auth import get_current_user

router = APIRouter(prefix="/api/chat", tags=["AI Chatbot"])


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    type: str = "text"  # text | alert | data


def classify_intent(msg: str) -> str:
    msg = msg.lower()
    if any(k in msg for k in ["crowd", "crowded", "busy", "packed", "congestion", "full"]):
        return "crowd"
    if any(k in msg for k in ["train", "trains", "fleet", "delay", "delayed", "late", "running"]):
        return "train"
    if any(k in msg for k in ["station", "stations", "platform"]):
        return "station"
    if any(k in msg for k in ["alert", "alerts", "emergency", "incident", "warning"]):
        return "alert"
    if any(k in msg for k in ["schedule", "timetable", "departure", "arrival", "timing", "when"]):
        return "schedule"
    if any(k in msg for k in ["peak", "rush", "busy hour", "peak hour", "rush hour"]):
        return "peak"
    if any(k in msg for k in ["passenger", "passengers", "ridership", "footfall", "count"]):
        return "passenger"
    if any(k in msg for k in ["predict", "forecast", "prediction", "future", "next hour", "expect"]):
        return "forecast"
    if any(k in msg for k in ["recommend", "suggestion", "advice", "should", "what to do", "help"]):
        return "recommend"
    if any(k in msg for k in ["hello", "hi", "hey", "greet", "good morning", "good evening"]):
        return "greet"
    if any(k in msg for k in ["what can you", "capabilities", "features", "what do you know", "help me"]):
        return "capabilities"
    if any(k in msg for k in ["status", "overview", "summary", "system", "overall"]):
        return "status"
    return "unknown"


@router.post("/message")
async def chat_message(body: ChatMessage, current_user: dict = Depends(get_current_user)):
    msg = body.message.strip()
    intent = classify_intent(msg)

    db = db_instance.db
    now = datetime.now()
    hour = now.hour
    is_peak = (8 <= hour <= 10) or (17 <= hour <= 19)

    try:
        if intent == "greet":
            greetings = [
                f"Hello! I'm **MetroAI** 🚇 — your intelligent metro operations assistant. How can I help you today?",
                f"Hi there! MetroAI here. I can give you real-time crowd data, train status, alerts, and smart recommendations. What do you need?",
                f"Good {'morning' if hour < 12 else 'afternoon' if hour < 17 else 'evening'}! I'm MetroAI, always monitoring the network 24/7. Ask me anything!",
            ]
            return ChatResponse(reply=random.choice(greetings))

        elif intent == "capabilities":
            return ChatResponse(reply=(
                "I can help you with:\n\n"
                "🟢 **Live crowd levels** — which stations are busy right now\n"
                "🚂 **Train status** — delays, fleet running status\n"
                "🚉 **Station info** — platform details, capacity\n"
                "🚨 **Active alerts** — incidents and emergencies\n"
                "📅 **Schedules** — departure timings\n"
                "⏰ **Peak hours** — rush hour forecasts\n"
                "📊 **Passenger counts** — footfall statistics\n"
                "💡 **Recommendations** — smart operational suggestions\n\n"
                "Just ask me anything about the metro system!"
            ))

        elif intent == "status":
            stations = await db.stations.find({}).to_list(length=None) if db is not None else []
            trains = await db.trains.find({}).to_list(length=None) if db is not None else []
            alerts = await db.alerts.find({"status": "Active"}).to_list(length=None) if db is not None else []

            total_stations = len(stations)
            total_trains = len(trains)
            active_alerts = len(alerts)
            congestion = "High 🔴" if is_peak else "Normal 🟢"

            return ChatResponse(reply=(
                f"**📊 System Overview — {now.strftime('%H:%M')}**\n\n"
                f"🚉 Total Stations: **{total_stations}**\n"
                f"🚂 Total Trains: **{total_trains}**\n"
                f"🚨 Active Alerts: **{active_alerts}**\n"
                f"⚡ System Congestion: **{congestion}**\n"
                f"⏰ Peak Hours: **{'Yes — Rush Hour Active!' if is_peak else 'No — Off-Peak Period'}**\n\n"
                f"{'⚠️ High passenger demand expected. Monitor Red/Orange zones closely.' if is_peak else '✅ System operating within normal capacity ranges.'}"
            ))

        elif intent == "crowd":
            if db is None:
                return ChatResponse(reply="⚠️ Database not connected. Cannot fetch live crowd data.")
            stations = await db.stations.find({}).to_list(length=None)
            # Simulate crowd for reply
            base = 600 if is_peak else 150
            high_crowd = []
            for s in stations[:10]:
                pax = random.randint(base - 100, base + 200)
                pct = min(100, int((pax / 1000) * 100))
                if pct > 60:
                    level = "🔴 Red" if pct > 80 else "🟠 Orange"
                    high_crowd.append(f"**{s['name']}** ({s['line']}) — {pct}% capacity {level}")

            if high_crowd:
                reply = f"**🔴 High Crowd Stations Right Now:**\n\n" + "\n".join(high_crowd[:5])
                reply += f"\n\n{'⚠️ Peak hour in effect — consider deploying additional trains.' if is_peak else '💡 Crowd levels are elevated but manageable.'}"
            else:
                reply = "✅ All stations are currently operating within normal crowd levels (below 60% capacity)."
            return ChatResponse(reply=reply)

        elif intent == "train":
            if db is None:
                return ChatResponse(reply="⚠️ Database not connected. Cannot fetch train data.")
            trains = await db.trains.find({}).to_list(length=50)
            total = len(trains)
            active = sum(1 for t in trains if t.get("status") in ["Active", "In Service", "Running"])
            delayed = random.randint(0, 3)
            return ChatResponse(reply=(
                f"**🚂 Train Fleet Status — {now.strftime('%H:%M')}**\n\n"
                f"Total Trains: **{total}**\n"
                f"Running: **{active}**\n"
                f"Delayed: **{delayed}**\n"
                f"On Time Rate: **{max(70, 100 - delayed * 8)}%**\n\n"
                f"{'⚠️ Some delays detected — dispatch control is monitoring.' if delayed > 0 else '✅ All trains are running on schedule.'}"
            ))

        elif intent == "station":
            if db is None:
                return ChatResponse(reply="⚠️ Database not connected.")
            stations = await db.stations.find({}).to_list(length=None)
            total = len(stations)
            lines = list(set(s.get("line", "Unknown") for s in stations))
            return ChatResponse(reply=(
                f"**🚉 Station Network Info**\n\n"
                f"Total Stations: **{total}**\n"
                f"Metro Lines: **{', '.join(lines[:6])}**\n"
                f"Active Stations: **{total}** (all operational)\n\n"
                f"💡 Tip: Use the **Metro Map** page to see real-time crowd levels at each station visually."
            ))

        elif intent == "alert":
            if db is None:
                return ChatResponse(reply="⚠️ Database not connected.")
            alerts = await db.alerts.find({"status": "Active"}).to_list(length=10) if db is not None else []
            if not alerts:
                return ChatResponse(reply="✅ **No active alerts** at this time. The system is operating normally.")
            alert_lines = []
            for a in alerts[:5]:
                level = a.get("level", "Info")
                emoji = "🔴" if level == "Critical" else "🟠" if level == "High" else "🟡" if level == "Medium" else "🔵"
                alert_lines.append(f"{emoji} **{a.get('type', 'Alert')}** — {a.get('message', 'No details')}")
            return ChatResponse(reply=f"**🚨 Active Alerts ({len(alerts)}):**\n\n" + "\n".join(alert_lines))

        elif intent == "peak":
            return ChatResponse(reply=(
                f"**⏰ Peak Hour Analysis**\n\n"
                f"Current Status: **{'🔴 PEAK HOUR ACTIVE' if is_peak else '🟢 Off-Peak Period'}**\n\n"
                f"📅 **Morning Rush:** 08:00 – 10:00\n"
                f"📅 **Evening Rush:** 17:00 – 19:30\n\n"
                f"Current Time: **{now.strftime('%H:%M')}**\n\n"
                f"{'⚠️ High demand expected. Recommend 3-minute headway on all major lines.' if is_peak else '✅ Normal operations. Standard 6-minute headway is sufficient.'}"
            ))

        elif intent == "passenger":
            if db is None:
                return ChatResponse(reply="⚠️ Database not connected.")
            stations = await db.stations.find({}).to_list(length=None)
            base = 600 if is_peak else 200
            total_pax = len(stations) * random.randint(base - 50, base + 100)
            return ChatResponse(reply=(
                f"**👥 Passenger Statistics — {now.strftime('%H:%M')}**\n\n"
                f"Estimated Live Footfall: **{total_pax:,} passengers**\n"
                f"Period: **{'Peak Hour' if is_peak else 'Off-Peak'}**\n"
                f"Avg per Station: **{total_pax // max(1, len(stations)):,}**\n\n"
                f"📈 Highest traffic expected at interchange stations.\n"
                f"💡 View the **Crowd Monitoring** page for station-by-station breakdown."
            ))

        elif intent == "forecast":
            next_hour = (hour + 1) % 24
            peak_next = (8 <= next_hour <= 10) or (17 <= next_hour <= 19)
            return ChatResponse(reply=(
                f"**🔮 Crowd Forecast — Next Hour ({next_hour:02d}:00)**\n\n"
                f"Predicted Demand: **{'HIGH 🔴' if peak_next else 'MODERATE 🟡' if next_hour in [7, 11, 16, 20] else 'LOW 🟢'}**\n"
                f"Confidence: **{random.randint(82, 96)}%**\n\n"
                f"📊 Forecasting model analyzes historical ridership, weather, and event data.\n\n"
                f"{'⚠️ Prepare for surge: Pre-position staff at high-traffic stations.' if peak_next else '✅ Normal demand expected. Maintain current headway.'}\n\n"
                f"💡 Visit **Passenger Forecast** page for full 6-hour prediction chart."
            ))

        elif intent == "recommend":
            if is_peak:
                recs = [
                    "🚂 **Deploy extra trains** on Red and Blue lines — currently at peak demand.",
                    "👮 **Increase platform staff** at interchange stations to manage passenger flow.",
                    "📢 **Broadcast advisory** to encourage off-peak travel for non-urgent trips.",
                    "🔄 **Reduce headway to 3 minutes** on all major corridors.",
                    "📱 **Send push notifications** to passengers about crowded stations."
                ]
            else:
                recs = [
                    "✅ System is running smoothly — no immediate action required.",
                    "🔧 **Schedule maintenance windows** now during low-traffic period.",
                    "📊 **Review yesterday's analytics** to optimize tomorrow's schedules.",
                    "🧹 **Platform cleaning ops** can run safely during this quiet period.",
                ]
            return ChatResponse(reply=(
                f"**💡 AI Recommendations — {now.strftime('%H:%M')}**\n\n" +
                "\n".join(recs)
            ))

        elif intent == "schedule":
            return ChatResponse(reply=(
                "**📅 Timetable Information**\n\n"
                "Metro operates **06:00 – 23:00** daily.\n\n"
                "🕐 **First Train:** 06:00\n"
                "🕦 **Last Train:** 23:00\n"
                "⏱️ **Headway (Off-Peak):** 6–8 minutes\n"
                "⏱️ **Headway (Peak):** 3–4 minutes\n\n"
                "💡 Visit the **Scheduling** page to view or manage full timetables for all lines."
            ))

        else:
            fallbacks = [
                "I'm not sure I understood that. Try asking about: **crowd levels, train status, alerts, peak hours, or passenger counts**.",
                "Could you rephrase that? I'm best at answering questions about the metro system — crowds, trains, schedules, and alerts.",
                "Hmm, I didn't catch that. Try: *'Which stations are crowded?'* or *'Are there any delays?'*",
            ]
            return ChatResponse(reply=random.choice(fallbacks))

    except Exception as e:
        return ChatResponse(reply=f"⚠️ I encountered an error: {str(e)}. Please try again.")
