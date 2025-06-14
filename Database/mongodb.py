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

    async def create_subscription(self, user_id: str, plan_id: str, is_trial_register: bool = False) -> dict:
        plan = await self.get_plan_by_id(plan_id)
        now = datetime.now(timezone.utc)
        if not plan:
            raise ValueError("Invalid plan ID")
        if not is_trial_register:
            end_date = int((now + timedelta(days=plan["duration_days"])).timestamp())
        else:
            end_date = int((now + timedelta(days=15)).timestamp())
        
        subscription_doc = {
            "user_id": user_id,
            "plan_id": plan_id,
            "start_date": int(now.timestamp()),
            "end_date": end_date,
            "is_active": True,
            "payment_status": "active",
            "created_at": int(now.timestamp())
        }
        
        result = await self.subscriptions.insert_one(subscription_doc)
        subscription_doc["_id"] = result.inserted_id
        return subscription_doc

    async def renew_subscription(self, user_id: str, plan_id: str) -> dict:
        plan = await self.get_plan_by_id(plan_id)
        if not plan:
            raise ValueError("Invalid plan ID")

        now = datetime.now(timezone.utc)
        end_date = int((now + timedelta(days=plan["duration_days"])).timestamp())

        filter = {
            "user_id": user_id,
        }
        update = {
            "$set": {
                "plan_id": plan_id,
                "end_date": end_date,
                "is_active": True,
                "payment_status": "active",
            }
        }

        result = await self.subscriptions.find_one_and_update(
            filter,
            update,
            return_document=True
        )

        if result:
            return result
        else:
            raise ValueError("No active subscription found for this user")

    async def get_user_subscription(self, user_id: str) -> Optional[dict]:
        return await self.subscriptions.find_one({"user_id": user_id})

    async def cancel_subscription(self, user_id: str) -> bool:
        now = datetime.now(timezone.utc)
        result = await self.subscriptions.update_one(
            {
                "user_id": user_id,
                "is_active": True
            },
            {
                "$set": {
                    "plan_id": "free",
                    "is_active": False,
                    "payment_status": "ended",
                    "end_date": int(now.timestamp()),
                    "updated_at": int(now.timestamp())
                }
            }
        )
        return result.modified_count > 0

    async def check_trial_ability(self, user_id: str) -> bool:
        result = await self.subscriptions.find_one({
            "user_id": user_id,
        })
        if result:
            return False
        return True

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

    async def get_ploplus_subscription(self, user_id: str) -> dict:
        return await self.subscriptions.find_one({"user_id": user_id, "plan_id": "pro_plus"})