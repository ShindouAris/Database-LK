from fastapi import APIRouter, HTTPException, Request
from utils.tknh import gen_qr
import os
from utils.webhook import send, build_transaction_embed
from utils.LRU_CACHE import LRUCache
from asyncio import Lock
from Database.mongodb import MongoDB
from datetime import datetime, timezone
from pydantic import BaseModel
from Database.plans import get_plan_by_id
import urllib.parse
from utils.payment import Payment
from utils.verify import is_valid_signature
import asyncio

ACCOUNT_NUMBER = os.environ.get("ACCOUNT_NUMBER")
ACCOUNT_NAME = os.environ.get("ACCOUNT_NAME")
MONGODB_URL = os.environ.get("MONGODB_URL")
MONGODB_USERPASSWORD = os.environ.get("MONGODB_USERPASSWORD")
MONGODB_USERNAME = os.environ.get("MONGODB_USERNAME")
ADMIN_KEY = os.environ.get("ADMIN_KEY")


class SubscriptionRequest(BaseModel):
    user_id: str
    plan_id: str

class SubscriptionResponse(BaseModel):
    plan_id: str
    start_date: int | None = None
    end_date: int | None = None
    is_active: bool = False
    qr_code: str | None = None
    

class RegisterResponse(BaseModel):
    success: bool
    qr_code: str
    message: str

class SubscriptionVerify(BaseModel):
    success: bool
    message: str

class SubscriptionVerifyRequest(BaseModel):
    admin_key: str
    user_id: str
    plan_id: str

class GetQRCodeRequest(BaseModel):
    user_id: str
    plan_id: str

class RequestCache(LRUCache):
    def __init__(self, capacity: int, expire_seconds: int):
        super().__init__(capacity, expire_seconds)
        self.lock = Lock()

    async def get_request(self, user_id: str):
        async with self.lock:
            try:
                return self.get(user_id)
            except KeyError:
                return None

    async def add_request(self, user_id: str, request_data: dict):
        async with self.lock:
            self.put(user_id, request_data)

    async def delete_request(self, user_id: str):
        async with self.lock:
            self.delete(user_id)

class OrderCodeCache(LRUCache):
    def __init__(self, capacity: int, expire_seconds: int):
        super().__init__(capacity, expire_seconds)
        self.lock = Lock()

    async def get_order_code(self, orderID: str):
        async with self.lock:
            try:
                return self.get(orderID)
            except KeyError:
                return None
    
    async def put_order_code(self, orderID: str, data: dict):
        async with self.lock:
            self.put(orderID, data)

    async def delete_order_code(self, orderID: str):
        async with self.lock:
            self.delete(orderID)

    async def get_all_order_codes(self):
        async with self.lock:
            return self.cache.keys()

class SubscriptionRoute(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(prefix="/subscription", *args, **kwargs)
        self.add_event_handler("startup", self.lifespan)
        self.add_api_route("/user-plans/register", self.register_subscription, methods=["POST"])
        self.add_api_route("/user-plans/{user_id}", self.get_user_subscription, methods=["GET"])
        self.add_api_route("/admin/verify", self.verify_subscription, methods=["POST"])
        self.add_api_route("/webhook", self.webhook, methods=["POST"])

        self.request_cache = RequestCache(10000, -1) 
        self.order_code_cache = OrderCodeCache(10000, -1)
        self.userdb = MongoDB(MONGODB_URL.format(username=urllib.parse.quote_plus(MONGODB_USERNAME), password=urllib.parse.quote_plus(MONGODB_USERPASSWORD)))
        self.payment = Payment()

    async def auto_cancel_transaction(self):
        while True:
            await asyncio.sleep(60)
            async with self.order_code_cache.lock:
                order_codes = list(self.order_code_cache.cache.keys())
            for order_code in order_codes:
                order_data = await self.order_code_cache.get_order_code(order_code)
                if order_data:
                    if order_data.get("created_at") + 300 < datetime.now(timezone.utc).timestamp():
                        self.payment.logger.info(f"Auto-canceling order: {order_code} due to timeout")
                        self.payment.cancel(order_code)
                        await self.order_code_cache.delete_order_code(order_code)

    async def lifespan(self):
        await self.userdb.init_db()
        asyncio.create_task(self.auto_cancel_transaction())


    async def check_subscription_expiry(self, subscription: dict) -> bool:
        """Check if a subscription is expired and update its status if needed."""
        if not subscription.get("is_active"):
            return False

        if subscription.get("end_date") and subscription.get("end_date") <= int(datetime.now(timezone.utc).timestamp()):
            await self.userdb.cancel_subscription(subscription.get("user_id"))
            return False

        return True

    async def register_subscription(self, request: SubscriptionRequest) -> RegisterResponse:
        """Register a new subscription request."""
        current_sub = await self.userdb.get_subscription(request.user_id)
        if current_sub:
            is_active = await self.check_subscription_expiry(current_sub)
            if is_active:
                raise HTTPException(status_code=400, detail="User already has an active subscription")
            
   
        user = await self.userdb.get_user(request.user_id)
        if not user: 
            await self.userdb.create_user(request.user_id)
        

        plan = get_plan_by_id(request.plan_id)
        if not plan:
            raise HTTPException(status_code=400, detail="Invalid plan ID")

        existing_request = await self.request_cache.get_request(request.user_id)

        if existing_request:
            if existing_request.get("plan_id") == request.plan_id:
                return RegisterResponse(
                    success=False,
                    qr_code=existing_request.get("qr_code"),
                    message="User already has a pending request"
                )
            else:
                await self.request_cache.delete_request(request.user_id)
                self.payment.cancel(existing_request.get("order_code"))
                await self.order_code_cache.delete_order_code(existing_request.get("order_code"))
                
        
        items = self.payment.choose_items(request.plan_id)
        if not items:
            raise HTTPException(status_code=400, detail="Invalid plan ID")

        payment_data = self.payment.create(items, plan.get("price"))

        request_data = {
            "plan_id": request.plan_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "qr_code": payment_data.get("qr_code"),
            "order_code": payment_data.get("order_code"),
        }
        order_data = {
            "user_id": request.user_id,
            "plan_id": request.plan_id,
            "created_at": datetime.now(timezone.utc).timestamp(),
        }

        await self.request_cache.add_request(request.user_id, request_data)
        await self.order_code_cache.put_order_code(payment_data.get("order_code"), order_data)

        await send( await build_transaction_embed(
            user_id=request.user_id,
            plan_id=request.plan_id,
            amount=plan.get("price"),
        ))

        return RegisterResponse(
            success=True,
            qr_code=payment_data.get("qr_code"),
            message="Subscription request sent successfully"
        )

    async def get_user_subscription(self, user_id: str) -> SubscriptionResponse:
        """Get user's current subscription or pending request."""
        subscription = await self.userdb.get_subscription(user_id)
        if subscription:
            is_active = await self.check_subscription_expiry(subscription)
            
            return SubscriptionResponse(
                plan_id=subscription.get("plan_id"),
                start_date=subscription.get("start_date"),
                end_date=subscription.get("end_date"),
                is_active=is_active,
                qr_code=None,
                message="Subscription found"
            )

        pending_request = await self.request_cache.get_request(user_id)
        if pending_request:
            plan = get_plan_by_id(pending_request['plan_id'])
            if plan:
                return SubscriptionResponse(
                    plan_id=pending_request['plan_id'],
                    start_date=datetime.fromisoformat(pending_request['timestamp']),
                    end_date=None,
                    is_active=False,
                    qr_code=pending_request.get('qr_code'),
                    message="Pending request found"
                )

        return SubscriptionResponse(
            plan_id="free",
            start_date=0,
            end_date=None,
            is_active=False,
            qr_code=None,
        )

    async def verify_subscription(self, request: SubscriptionVerifyRequest) -> SubscriptionVerify:
        """Verify a subscription request."""

        if request.admin_key != ADMIN_KEY:
            raise HTTPException(status_code=401, detail="Invalid admin key")

        await self.userdb.create_subscription(request.user_id, request.plan_id)

        return SubscriptionVerify(
            success=True,
            message=f"Subscription verified successfully for {request.user_id} with plan {request.plan_id}",
        )
 
    async def webhook(self, request: Request):
        data = await request.json()
        if not is_valid_signature(data, data.get("signature")):
            return {"success": False, "message": "Invalid signature"}
                
        if self.payment.check_payment_status(data):
            order_data = await self.order_code_cache.get_order_code(data.get("orderCode"))
            if not order_data:
                return {"success": False, "message": "Order not found"}
            await self.userdb.create_subscription(order_data.get("user_id"), order_data.get("plan_id"))
            await self.order_code_cache.delete_order_code(data.get("orderCode"))
            return {"success": True}


        
