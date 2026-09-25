from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from bson import ObjectId
import random
from backend.database import db_instance
from backend.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Analytics & Dashboard"])

@router.get("/dashboard")
async def get_dashboard_summary(current_user: dict = Depends(get_current_user)):
    db = db_instance.db
    if db is None:
        return get_mock_dashboard()
        
    try:
        # 1. KPI Counts
        total_stations = await db.stations.count_documents({})
        active_trains = await db.trains.count_documents({"status": "In Service"})
        active_alerts = await db.alerts.count_documents({"status": "Active"})
        
        # Calculate delay percentage from recent schedules
        total_sched = await db.schedules.count_documents({})
        delayed_sched = await db.schedules.count_documents({"status": "Delayed"})
        delay_pct = round((delayed_sched / total_sched) * 100, 1) if total_sched > 0 else 2.5
        
        # Calculate simulated ridership today
        riders_today = 348500 + random.randint(-5000, 5000)
        
        # 2. Daily Ridership (7 days)
        ridership_trend = []
        now = datetime.now()
        for i in range(6, -1, -1):
            date_str = (now - timedelta(days=i)).strftime("%a")
            # Peak on weekdays, lower on weekends
            is_weekend = (now - timedelta(days=i)).weekday() >= 5
            base = 220000 if is_weekend else 360000
            ridership_trend.append({
                "name": date_str,
                "riders": base + random.randint(-15000, 15000)
            })
            
        # 3. Crowd Density by Line
        lines = ["Red line", "Yellow line", "Blue line", "Pink line", "Magenta line", "Violet line"]
        crowd_by_line = []
        for line in lines:
            # Aggregate crowd percentages for stations on this line
            stations_cursor = db.stations.find({"line": line}, {"_id": 1})
            station_ids = [s["_id"] for s in await stations_cursor.to_list(length=100)]
            
            avg_density = 45 # default
            if station_ids:
                crowd_cursor = db.crowd_data.find({"station_id": {"$in": station_ids}}).sort("timestamp", -1).limit(len(station_ids))
                crowd_logs = await crowd_cursor.to_list(length=100)
                if crowd_logs:
                    avg_density = sum(c.get("crowd_percentage", 0) for c in crowd_logs) // len(crowd_logs)
            
            crowd_by_line.append({
                "subject": line.replace(" line", ""),
                "A": avg_density,
                "B": min(100, avg_density + random.randint(-10, 15)), # Comparison metric
                "fullMark": 100
            })
            
        # 4. Top 5 Congested Stations
        congested_stations = []
        stations_cursor = db.stations.find({}).limit(5)
        async for s in stations_cursor:
            last_crowd = await db.crowd_data.find_one({"station_id": s["_id"]}, sort=[("timestamp", -1)])
            pct = last_crowd.get("crowd_percentage", random.randint(30, 85)) if last_crowd else random.randint(30, 85)
            congested_stations.append({
                "name": s.get("station_name", s.get("name", "Unknown")),
                "density": pct
            })
        congested_stations.sort(key=lambda x: x["density"], reverse=True)
        
        # 5. Top 5 Packed Trains (Train Occupancy)
        trains_cursor = db.trains.find({"status": "In Service"}).limit(5)
        train_occupancy = []
        async for t in trains_cursor:
            pct = int((t.get("current_occupancy", 0) / t.get("capacity", 1200)) * 100)
            train_occupancy.append({
                "name": t["train_number"],
                "occupancy": pct
            })
        train_occupancy.sort(key=lambda x: x["occupancy"], reverse=True)
        # Pad with mock data if empty
        if not train_occupancy:
            train_occupancy = [
                {"name": "TR-RED-01", "occupancy": 82},
                {"name": "TR-YEL-03", "occupancy": 75},
                {"name": "TR-BLU-02", "occupancy": 64},
                {"name": "TR-PNK-01", "occupancy": 58},
                {"name": "TR-MAG-02", "occupancy": 49}
            ]
            
        # 6. Delay Statistics
        delay_stats = [
            {"name": "Signal Issue", "value": 45},
            {"name": "Track Work", "value": 20},
            {"name": "Crowd Delay", "value": 15},
            {"name": "Weather", "value": 12},
            {"name": "Emergency", "value": 8}
        ]
        
        # 7. Recent Activity Table
        recent_activities = []
        alerts_cursor = db.alerts.find({}).sort("timestamp", -1).limit(6)
        async for a in alerts_cursor:
            recent_activities.append({
                "id": str(a["_id"]),
                "time": a["timestamp"].strftime("%H:%M"),
                "event": a["message"],
                "type": a["type"],
                "status": a["status"]
            })
            
        # 8. Missing Charts: Route Performance, Passenger Forecast, Alert Statistics
        route_performance = [
            {"name": "Red Line", "efficiency": 92},
            {"name": "Yellow Line", "efficiency": 85},
            {"name": "Blue Line", "efficiency": 78},
            {"name": "Pink Line", "efficiency": 88},
            {"name": "Magenta Line", "efficiency": 95}
        ]
        passenger_forecast = [
            {"time": "08:00", "predicted": 45000, "actual": 42000},
            {"time": "09:00", "predicted": 55000, "actual": 58000},
            {"time": "10:00", "predicted": 40000, "actual": 39000},
            {"time": "11:00", "predicted": 25000, "actual": 26000},
            {"time": "12:00", "predicted": 22000, "actual": 21000},
            {"time": "13:00", "predicted": 24000, "actual": 23500}
        ]
        alert_statistics = [
            {"name": "Overcrowding", "count": 12},
            {"name": "Train Delay", "count": 8},
            {"name": "Emergency", "count": 2},
            {"name": "Platform Congestion", "count": 5}
        ]
        
        # 9. AI Operational Insights
        ai_insights = [
            {"type": "Actionable", "message": "Increase train frequency on Yellow Line between 8 AM-10 AM to reduce 85% congestion."},
            {"type": "Predictive", "message": "Rajiv Chowk is predicted to exceed capacity within 20 minutes. Consider passenger diversion."},
            {"type": "Efficiency", "message": "Magenta Line is operating at 95% efficiency. No immediate schedule changes required."},
            {"type": "Warning", "message": "Delay trend detected on Blue Line due to recurring signal issues. Maintenance recommended."}
        ]
            
        return {
            "kpis": {
                "totalStations": total_stations,
                "activeTrains": active_trains,
                "delayedTrains": delayed_sched,
                "averageOccupancy": 68,
                "passengersToday": riders_today,
                "peakHour": "08:30 - 09:45",
                "activeAlerts": active_alerts,
                "delayPercentage": delay_pct
            },
            "charts": {
                "ridershipTrend": ridership_trend,
                "crowdDensity": crowd_by_line,
                "stationCongestion": congested_stations,
                "trainOccupancy": train_occupancy,
                "delayStatistics": delay_stats,
                "routePerformance": route_performance,
                "passengerForecast": passenger_forecast,
                "alertStatistics": alert_statistics
            },
            "recentActivity": recent_activities,
            "aiInsights": ai_insights
        }
        
    except Exception as e:
        print(f"Error compiling dashboard metrics: {e}")
        return get_mock_dashboard()

def get_mock_dashboard():
    # Return realistic seed mock state if DB fails to query or is blank
    return {
        "kpis": {
            "totalStations": 286,
            "activeTrains": 45,
            "passengersToday": 348500,
            "peakHour": "08:30 - 09:45",
            "activeAlerts": 3,
            "delayPercentage": 4.2,
            "delayedTrains": 5,
            "averageOccupancy": 72
        },
        "charts": {
            "ridershipTrend": [
                {"name": "Wed", "riders": 352000},
                {"name": "Thu", "riders": 361000},
                {"name": "Fri", "riders": 374000},
                {"name": "Sat", "riders": 210000},
                {"name": "Sun", "riders": 185000},
                {"name": "Mon", "riders": 348000},
                {"name": "Tue", "riders": 359000}
            ],
            "crowdDensity": [
                {"subject": "Red", "A": 55, "B": 60, "fullMark": 100},
                {"subject": "Yellow", "A": 82, "B": 85, "fullMark": 100},
                {"subject": "Blue", "A": 74, "B": 70, "fullMark": 100},
                {"subject": "Pink", "A": 42, "B": 50, "fullMark": 100},
                {"subject": "Magenta", "A": 60, "B": 65, "fullMark": 100},
                {"subject": "Violet", "A": 49, "B": 55, "fullMark": 100}
            ],
            "stationCongestion": [
                {"name": "Rajiv Chowk", "density": 89},
                {"name": "Kashmere Gate", "density": 82},
                {"name": "Hauz Khas", "density": 78},
                {"name": "Central Secretariat", "density": 71},
                {"name": "Inderlok", "density": 65}
            ],
            "trainOccupancy": [
                {"name": "TR-YEL-02", "occupancy": 92},
                {"name": "TR-BLU-05", "occupancy": 85},
                {"name": "TR-RED-01", "occupancy": 78},
                {"name": "TR-MAG-01", "occupancy": 69},
                {"name": "TR-PNK-03", "occupancy": 52}
            ],
            "delayStatistics": [
                {"name": "Signal Issue", "value": 45},
                {"name": "Track Work", "value": 20},
                {"name": "Crowd Delay", "value": 15},
                {"name": "Weather", "value": 12},
                {"name": "Emergency", "value": 8}
            ]
        },
        "recentActivity": [
            {"id": "1", "time": "18:42", "event": "Critical overcrowding at Rajiv Chowk platform 1.", "type": "Overcrowding", "status": "Active"},
            {"id": "2", "time": "18:30", "event": "Train TR-RED-01 delayed by 12 mins at Jhil Mil.", "type": "Train Delay", "status": "Active"},
            {"id": "3", "time": "17:15", "event": "Platform congestion warning at Hauz Khas.", "type": "Platform Congestion", "status": "Active"},
            {"id": "4", "time": "16:20", "event": "Scheduled track inspection completed at Netaji Subhash Place.", "type": "Info", "status": "Resolved"}
        ],
        "aiInsights": [
            {"type": "Actionable", "message": "Increase train frequency on Yellow Line between 8 AM-10 AM to reduce 85% congestion."},
            {"type": "Predictive", "message": "Rajiv Chowk is predicted to exceed capacity within 20 minutes. Consider passenger diversion."}
        ]
    }
