"""
Migration script: Copies all collections from local MongoDB to MongoDB Atlas
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

LOCAL_URI = "mongodb://localhost:27017"
ATLAS_URI = "mongodb+srv://tejaswachinnu_db_user:UYFbeidlXpJKnXSe@alaram.fifboex.mongodb.net/?appName=Alaram"
DB_NAME = "ai_metroflow"

async def migrate():
    print("Connecting to local MongoDB...")
    local_client = AsyncIOMotorClient(LOCAL_URI)
    local_db = local_client[DB_NAME]

    print("Connecting to MongoDB Atlas...")
    atlas_client = AsyncIOMotorClient(ATLAS_URI)
    atlas_db = atlas_client[DB_NAME]

    # Test Atlas connection
    await atlas_client.admin.command('ping')
    print("Atlas connection successful!\n")

    collections = await local_db.list_collection_names()
    print(f"Found {len(collections)} collections to migrate: {collections}\n")

    total_migrated = 0

    for col_name in collections:
        local_col = local_db[col_name]
        atlas_col = atlas_db[col_name]

        # Count documents in local
        count = await local_col.count_documents({})
        if count == 0:
            print(f"  Skipping '{col_name}' - empty collection")
            continue

        print(f"  Migrating '{col_name}' ({count} documents)...")

        # Drop existing atlas collection to avoid duplicates
        await atlas_col.drop()

        # Read all documents from local
        docs = []
        async for doc in local_col.find({}):
            docs.append(doc)

        # Insert in batches of 500
        batch_size = 500
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i+batch_size]
            await atlas_col.insert_many(batch)

        # Verify
        atlas_count = await atlas_col.count_documents({})
        print(f"  OK '{col_name}': {atlas_count}/{count} documents migrated")
        total_migrated += atlas_count

    print(f"\nMigration complete! Total documents migrated: {total_migrated}")
    print(f"Database '{DB_NAME}' is now live on MongoDB Atlas!")

    local_client.close()
    atlas_client.close()

if __name__ == "__main__":
    asyncio.run(migrate())
