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

ACCOUNT_NUMBER = os.getenv("ACCOUNT_NUMBER")
ACCOUNT_NAME = os.getenv("ACCOUNT_NAME")
MONGODB_URL = os.getenv("MONGODB_URL")
MONGODB_USERPASSWORD = os.getenv("MONGODB_USERPASSWORD")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME")
ADMIN_KEY = os.getenv("ADMIN_KEY")


class SubscriptionRequest(BaseModel):
    user_id: str
    plan_id: str

class SubscriptionResponse(BaseModel):
    plan_id: str
    start_date: datetime
    end_date: int
    is_active: bool
    qr_code: str | None
    

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

    def get_order_code(self, orderID: str):
        try:
            return self.get(orderID)
        except KeyError:
            return None
    
    def put_order_code(self, orderID: str, data: dict):
        self.put(orderID, data)

    def delete_order_code(self, orderID: str):
        self.delete(orderID)

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

    async def lifespan(self):
        await self.userdb.init_db()

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
            return RegisterResponse(
                success=False,
                qr_code=existing_request.get("qr_code"),
                message="User already has a pending request"
            )

        payment_data = self.payment.create(request.user_id, plan.get("price"))

        request_data = {
            "plan_id": request.plan_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "qr_code": payment_data.get("qr_code"),
        }
        order_data = {
            "user_id": request.user_id,
            "plan_id": request.plan_id,
        }

        await self.request_cache.add_request(request.user_id, request_data)
        self.order_code_cache.put_order_code(payment_data.get("order_code"), order_data)

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

        raise HTTPException(status_code=404, detail="No subscription or pending request found")

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
            order_data = self.order_code_cache.get_order_code(data.get("orderCode"))
            if not order_data:
                return {"success": False, "message": "Order not found"}
            await self.userdb.create_subscription(order_data.get("user_id"), order_data.get("plan_id"))
            self.order_code_cache.delete_order_code(data.get("orderCode"))
            return {"success": True}


        
