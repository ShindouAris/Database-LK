from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from Database.plans import get_plan_by_id

class MongoDB:
    def __init__(self, mongo_url: str):
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client.locket_uploader
        
        self.users = self.db.users
        self.plans = self.db.plans
        self.subscriptions = self.db.subscriptions

    async def init_db(self):
        await self.users.create_index("uid", unique=True)
        await self.subscriptions.create_index([("user_id", 1), ("is_active", 1)])
        await self.plans.create_index("id", unique=True)

    async def get_user(self, uid: str) -> dict:
        return await self.users.find_one({"uid": uid})

    async def create_user(self, uid: str, email: Optional[str] = None) -> dict:
        user_doc = {
            "uid": uid,
            "email": email,
            "created_at": int(datetime.now(timezone.utc).timestamp()),
            "is_active": False,
        }
        await self.users.insert_one(user_doc)
        return user_doc

    async def update_user(self, uid: str, **update_data) -> dict:
        result = await self.users.find_one_and_update(
            {"uid": uid},
            {"$set": update_data},
            return_document=True
        )
        return result

    async def get_active_subscription(self, user_id: str) -> dict:
        return await self.subscriptions.find_one({
            "user_id": user_id,
            "is_active": True
        })

    async def create_subscription(self, user_id: str, plan_id: str) -> dict:
        plan = await self.get_plan_by_id(plan_id)
        if not plan:
            raise ValueError("Invalid plan ID")

        end_date = int((datetime.now(timezone.utc) + timedelta(days=plan["duration_days"])).timestamp())
        
        subscription_doc = {
            "user_id": user_id,
            "plan_id": plan_id,
            "start_date": int(datetime.now(timezone.utc).timestamp()),
            "end_date": end_date,
            "is_active": True,
            "payment_status": "active",
            "created_at": int(datetime.now(timezone.utc).timestamp())
        }
        
        result = await self.subscriptions.insert_one(subscription_doc)
        subscription_doc["_id"] = result.inserted_id
        return subscription_doc

    async def cancel_subscription(self, user_id: str) -> bool:
        now = datetime.now(timezone.utc)
        result = await self.subscriptions.update_one(
            {
                "user_id": user_id,
                "is_active": True
            },
            {
                "$set": {
                    "is_active": False,
                    "cancelled_at": int(now.timestamp()),
                    "updated_at": int(now.timestamp())
                }
            }
        )
        return result.modified_count > 0

    async def get_user_plans(self, user_id: str) -> List[dict]:
        cursor = self.plans.find({
            "_id": {
                "$in": await self.subscriptions.distinct(
                    "plan_id",
                    {"user_id": user_id}
                )
            }
        })
        return await cursor.to_list(None)

    async def create_plan(self, id: str, name: str, price: int, duration_days: int,
                         max_uploads: int, perks: Dict[str, bool],
                         description: Optional[str] = None) -> dict:
        plan_doc = {
            "id": id,
            "name": name,
            "price": price,
            "duration_days": duration_days,
            "max_uploads": max_uploads,
            "perks": perks,
            "description": description,
            "is_active": False,
            "created_at": int(datetime.now(timezone.utc).timestamp())
        }
        await self.plans.insert_one(plan_doc)
        return plan_doc

    async def get_all_active_plans(self) -> List[dict]:
        cursor = self.plans.find({"is_active": True})
        return await cursor.to_list(None)

    async def get_plan_by_id(self, plan_id: str) -> dict:
        return get_plan_by_id(plan_id)

    async def get_subscription(self, user_id: str) -> dict:
        return await self.subscriptions.find_one({"user_id": user_id}) 