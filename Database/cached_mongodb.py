from typing import Optional, Dict, List
from datetime import datetime, timedelta, timezone
from utils.LRU_CACHE import LRUCache
from Database.mongodb import MongoDB
from Database.plans import get_plan_by_id

class CachedMongoDB:
    def __init__(self, mongo_url: str, cache_capacity: int = 1000, cache_expire_seconds: int = 3600):
        self.db = MongoDB(mongo_url)
        # Cache for user data
        self.user_cache = LRUCache(cache_capacity, cache_expire_seconds)
        # Cache for subscription data
        self.subscription_cache = LRUCache(cache_capacity, cache_expire_seconds)
        # Cache for plan data
        self.plan_cache = LRUCache(cache_capacity, cache_expire_seconds)
        # Cache for trial check results
        self.trial_check_cache = LRUCache(cache_capacity, cache_expire_seconds)

    async def init_db(self):
        await self.db.init_db()

    async def get_user(self, uid: str) -> dict:
        try:
            return self.user_cache.get(uid)
        except KeyError:
            user = await self.db.get_user(uid)
            if user:
                self.user_cache.put(uid, user)
            return user

    async def create_user(self, uid: str, email: Optional[str] = None) -> dict:
        user = await self.db.create_user(uid, email)
        self.user_cache.put(uid, user)
        return user

    async def update_user(self, uid: str, **update_data) -> dict:
        user = await self.db.update_user(uid, **update_data)
        if user:
            self.user_cache.put(uid, user)
        return user

    async def get_active_subscription(self, user_id: str) -> dict:
        cache_key = f"active_{user_id}"
        try:
            return self.subscription_cache.get(cache_key)
        except KeyError:
            subscription = await self.db.get_active_subscription(user_id)
            if subscription:
                self.subscription_cache.put(cache_key, subscription)
            return subscription

    async def create_subscription(self, user_id: str, plan_id: str, is_trial_register: bool = False) -> dict:
        subscription = await self.db.create_subscription(user_id, plan_id, is_trial_register)
        # Update both active and general subscription caches
        self.subscription_cache.put(f"active_{user_id}", subscription)
        self.subscription_cache.put(user_id, subscription)
        # Invalidate trial check cache since user now has a subscription
        self.trial_check_cache.delete(user_id)
        return subscription

    async def get_user_subscription(self, user_id: str) -> Optional[dict]:
        try:
            return self.subscription_cache.get(user_id)
        except KeyError:
            subscription = await self.db.get_user_subscription(user_id)
            if subscription:
                self.subscription_cache.put(user_id, subscription)
            return subscription

    async def renew_subscription(self, user_id: str, plan_id: str) -> dict:
        subscription = await self.db.renew_subscription(user_id, plan_id)
        if subscription:
            self.subscription_cache.put(f"active_{user_id}", subscription)
            self.subscription_cache.put(user_id, subscription)
            self.trial_check_cache.delete(user_id)
        return subscription

    async def cancel_subscription(self, user_id: str) -> bool:
        success = await self.db.cancel_subscription(user_id)
        if success:
            # Remove from both caches
            self.subscription_cache.delete(f"active_{user_id}")
            self.subscription_cache.delete(user_id)
        return success

    async def check_trial_ability(self, user_id: str) -> bool:
        try:
            return self.trial_check_cache.get(user_id)
        except KeyError:
            result = await self.db.check_trial_ability(user_id)
            self.trial_check_cache.put(user_id, result)
            return result

    async def create_plan(self, id: str, name: str, price: int, duration_days: int,
                         max_uploads: int, perks: Dict[str, bool],
                         description: Optional[str] = None) -> dict:
        plan = await self.db.create_plan(id, name, price, duration_days, max_uploads, perks, description)
        self.plan_cache.put(id, plan)
        return plan

    async def get_all_active_plans(self) -> List[dict]:
        cache_key = "all_active_plans"
        try:
            return self.plan_cache.get(cache_key)
        except KeyError:
            plans = await self.db.get_all_active_plans()
            self.plan_cache.put(cache_key, plans)
            return plans

    async def get_plan_by_id(self, plan_id: str) -> dict:
        try:
            return self.plan_cache.get(plan_id)
        except KeyError:
            plan = get_plan_by_id(plan_id)
            if plan:
                self.plan_cache.put(plan_id, plan)
            return plan

    async def get_subscription(self, user_id: str) -> dict:
        try:
            return self.subscription_cache.get(user_id)
        except KeyError:
            subscription = await self.db.get_ploplus_subscription(user_id)
            if subscription:
                self.subscription_cache.put(user_id, subscription)
            return subscription 