import asyncio
import os
import sys
import math
sys.path.append(os.path.abspath("."))
from backend.database import connect_db, db_instance

def distance(lat1, lon1, lat2, lon2):
    # simple euclidean distance for sorting
    return math.hypot(lat1 - lat2, lon1 - lon2)

async def fix_routes():
    await connect_db()
    db = db_instance.db
    
    stations = await db.stations.find({}).to_list(length=None)
    
    # Group by line
    lines = {}
    for s in stations:
        line = s.get("line")
        if line not in lines:
            lines[line] = []
        lines[line].append(s)
        
    for line, stns in lines.items():
        if len(stns) < 2:
            continue
            
        # Find the two stations furthest apart to use one as the starting terminal
        max_dist = -1
        start_node = stns[0]
        
        for s1 in stns:
            for s2 in stns:
                d = distance(s1["latitude"], s1["longitude"], s2["latitude"], s2["longitude"])
                if d > max_dist:
                    max_dist = d
                    start_node = s1
                    
        # Greedy Nearest Neighbor to reconstruct the path
        unvisited = [s for s in stns if s["_id"] != start_node["_id"]]
        current = start_node
        path = [current]
        
        while unvisited:
            nearest = None
            min_dist = float('inf')
            for u in unvisited:
                d = distance(current["latitude"], current["longitude"], u["latitude"], u["longitude"])
                if d < min_dist:
                    min_dist = d
                    nearest = u
            path.append(nearest)
            unvisited.remove(nearest)
            current = nearest
            
        # Now update distance_from_start_km sequentially (1, 2, 3, ...)
        for idx, p in enumerate(path):
            await db.stations.update_one(
                {"_id": p["_id"]},
                {"$set": {"distance_from_start_km": float(idx)}}
            )
            
    print("Fixed station sequences based on geographic nearest-neighbor!")

if __name__ == "__main__":
    asyncio.run(fix_routes())
