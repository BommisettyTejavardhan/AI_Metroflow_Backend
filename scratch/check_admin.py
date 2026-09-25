import asyncio
import os
import sys
sys.path.append(os.path.abspath("."))
from backend.database import connect_db, db_instance

async def check():
    await connect_db()
    db = db_instance.db
    u = await db.users.find_one({'email': 'admin@metroflow.com'})
    print("User found:", u)

if __name__ == "__main__":
    asyncio.run(check())
