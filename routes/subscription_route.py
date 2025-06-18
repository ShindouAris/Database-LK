from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
import logging
import os
from utils.webhook import send, build_transaction_embed, build_success_transaction_embed, build_fail_transaction_embed
from utils.LRU_CACHE import LRUCache
from asyncio import Lock
from Database.cached_mongodb import CachedMongoDB
from datetime import datetime, timezone
from pydantic import BaseModel
from Database.plans import get_plan_by_id
import urllib.parse
from utils.payment import Payment
import asyncio
from dotenv import load_dotenv
import re
from routes.models import *
load_dotenv()

ACCOUNT_NUMBER = os.environ.get("ACCOUNT_NUMBER")
ACCOUNT_NAME = os.environ.get("ACCOUNT_NAME")
MONGODB_URL = os.environ.get("MONGODB_URL")
MONGODB_USERPASSWORD = os.environ.get("MONGODB_USERPASSWORD")
MONGODB_USERNAME = os.environ.get("MONGODB_USERNAME")
ADMIN_KEY = os.environ.get("ADMIN_KEY")

logger = logging.getLogger(__name__)


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
            logger.info(f"Putting order code {orderID} into cache with data: {data}")
            self.put(orderID, data)

    async def delete_order_code(self, orderID: str):
        async with self.lock:
            self.delete(orderID)

    async def get_all_order_codes(self):
        async with self.lock:
            return self.cache.keys()

class UserSubscriptionCache(LRUCache):
    def __init__(self, capacity: int, expire_seconds: int):
        super().__init__(capacity, expire_seconds)

    def get_user_subscription(self, user_id: str):
        """Get user subscription from cache."""
        try:
            return self.get(user_id)
        except KeyError:
            return None

    def put_user_subscription(self, user_id: str, subscription_data: dict):
        """Put user subscription into cache."""
        self.put(user_id, subscription_data)

class SubscriptionRoute(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(prefix="/subscription", *args, **kwargs)
        self.add_event_handler("startup", self.lifespan)
        self.add_api_route("/user-plans/register", self.register_subscription, methods=["POST"])
        self.add_api_route("/user-plans/{user_id}", self.get_user_subscription, methods=["GET"])
        self.add_api_route("/admin/verify", self.verify_subscription, methods=["POST"])
        self.add_api_route("/webhook", self.webhook, methods=["POST"])
        self.add_api_route("/check-payment-status/{order_id}", self.check_payment_status, methods=["GET"])
        self.add_api_route("/payment/cancel/{order_id}", self.cancel_payment, methods=["POST"])
        self.add_api_route("/trialoffer/{user_id}", self.check_trial_ability, methods=["GET"])
        self.add_api_route("/trialoffer/register", self.register_trial, methods=["POST"])
        self.add_api_route("/get-all-pending-payments", self.get_all_pending_payment, methods=["GET"])

        self.request_cache = RequestCache(10000, -1) 
        self.order_code_cache = OrderCodeCache(10000, -1)
        self.user_subs_cache = UserSubscriptionCache(10000, 3600)

        self.userdb = CachedMongoDB(MONGODB_URL.format(username=urllib.parse.quote_plus(MONGODB_USERNAME), password=urllib.parse.quote_plus(MONGODB_USERPASSWORD)))
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
                        if order_data.get("is_finished"):
                            self.payment.logger.info(f"Order {order_code} already finished, skipping cancellation")
                        else:
                            await self.payment.cancel(order_code)
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

        plan = get_plan_by_id(request.plan_id)
        if not plan:
            raise HTTPException(status_code=400, detail="Invalid plan ID")

        existing_request = await self.request_cache.get_request(request.user_id)

        if existing_request:
            if existing_request.get("plan_id") == request.plan_id:
                return RegisterResponse(
                    success=False,
                    qr_code=existing_request.get("qr_code"),
                    message="User already has a pending request",
                    order_id=existing_request.get("order_code")
                )
            else:
                await self.request_cache.delete_request(request.user_id)
                await self.payment.cancel(existing_request.get("order_code"))
                await self.order_code_cache.delete_order_code(existing_request.get("order_code"))
                
        
        items = self.payment.choose_items(request.plan_id)
        if not items:
            raise HTTPException(status_code=400, detail="Invalid plan ID")

        payment_data = await self.payment.create(items, plan.get("price"))

        if not payment_data:
            raise HTTPException(status_code=500, detail="Error creating payment link")

        logger.info(f"Successfully created payment link for user {request.user_id} with plan {request.plan_id}")

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
            "is_finished": False
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
            order_id=payment_data.get("order_code"),
            qr_code=payment_data.get("qr_code"),
            message="Subscription request sent successfully"
        )

    async def get_user_subscription(self, user_id: str) -> SubscriptionResponse:
        """Get user's current subscription or pending request."""

        # Check in-memory cache first
        subscription = self.user_subs_cache.get_user_subscription(user_id)
        if not subscription:
            # Fallback to database
            subscription = await self.userdb.get_subscription(user_id)
            self.user_subs_cache.put_user_subscription(user_id, subscription)

        if not subscription:
            return self._free_subscription()

        is_active = await self.check_subscription_expiry(subscription)
        if not is_active:
            return self._free_subscription()

        return SubscriptionResponse(
            plan_id=subscription.get("plan_id", "free"),
            start_date=subscription.get("start_date"),
            end_date=subscription.get("end_date"),
            is_active=True,
            qr_code=None,
        )

    @staticmethod
    def _free_subscription() -> SubscriptionResponse:
        """Helper method to return the default free subscription."""
        return SubscriptionResponse(
            plan_id="free",
            start_date=None,
            end_date=None,
            is_active=False,
            qr_code=None,
        )

    @staticmethod
    def is_valid_uid(uid):
        pattern = r'^[a-zA-Z0-9]{28}$'
        return re.match(pattern, uid) is not None

    async def check_trial_ability(self, user_id: str) -> bool:
        """Check if the user is eligible for a trial subscription."""
        if await self.userdb.check_trial_ability(user_id):
            return True
        return False

    async def register_trial(self, request: TrailActivationRequest) -> TrailActivationResponse:
        """Register a trial subscription for the user."""
        if not request.user_id:
            raise HTTPException(status_code=400, detail="User ID is required")

        if not self.is_valid_uid(request.user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID format")

        if not await self.check_trial_ability(request.user_id):
            raise HTTPException(status_code=400, detail="User is not eligible for a trial subscription")
        logger.info(f"Activating trial subscription for user {request.user_id}")
        plan = get_plan_by_id("pro_plus")
        if not plan:
            raise HTTPException(status_code=400, detail="Invalid plan ID")

        try:
            await self.userdb.create_subscription(request.user_id, plan["id"], is_trial_register=True)
        except Exception as e:
            logger.error(f"Error creating trial subscription for user {request.user_id}: {e}")
            return TrailActivationResponse(
                success=False,
                message="Error creating trial subscription"
            )
        logger.info(f"Successfully activated trial subscription for user {request.user_id}")
        return TrailActivationResponse(
            success=True,
            message="Trial subscription activated successfully"
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

    async def check_payment_status(self, order_id) -> dict:
        """Check the payment status from the webhook data."""
        order_data = await self.order_code_cache.get_order_code(str(order_id))
        if not order_data:
            logger.error(f"Order code {order_id} not found in cache")
            return {
                "success": False,
                "message": "Order not found"
            }
        if order_data.get("is_finished"):
            logger.info(f"Order {order_id} is already finished")
            return {
                "success": True,
                "message": "Order Finished"
            }
        return {
            "success": False,
            "message": "Order not finished yet"
        }

    async def cancel_payment(self, order_id):
        """Cancel a payment request."""
        order_data = await self.order_code_cache.get_order_code(order_id)
        if order_data is None:
            logger.error(f"Order code {order_id} not found in cache")
            raise HTTPException(status_code=404, detail="Order not found")

        if order_data.get("is_finished"):
            logger.info(f"Order {order_id} is already finished, cannot cancel")
            raise HTTPException(status_code=400, detail="Order already finished")

        await self.payment.cancel(order_id)
        await self.order_code_cache.delete_order_code(order_id)
        await self.request_cache.delete_request(order_data.get("user_id"))

        return {"success": True, "message": "Payment cancelled successfully"}

    async def webhook(self, request: Request):
        data = await request.json()
        payload = data.get("data", {})
        order_code = payload.get("orderCode")

        if self.payment.check_payment_status(data):
            order_data = await self.order_code_cache.get_order_code(order_code)
            if not order_data:
                logger.error(f"Order code {order_code} not found in cache")
                return {"success": False, "message": "Order not found"}

            user = await self.userdb.get_user(order_data.get("user_id"))
            if not user and order_data.get("user_id") is not None:
                await self.userdb.create_user(order_data.get("user_id"))

            embed = await build_success_transaction_embed(
                user_id=order_data.get("user_id"),
                plan_id=order_data.get("plan_id")
            )


            logger.info(f"Payment successful for order: {order_code} - Plan: {order_data.get('plan_id')} - UserID: {order_data.get('user_id')}")
            subscription = await self.userdb.get_user_subscription(order_data.get("user_id"))
            if not subscription:
                logger.info(f"Creating new subscription for user {order_data.get('user_id')} with plan {order_data.get('plan_id')}")
                await self.userdb.create_subscription(order_data.get("user_id"), order_data.get("plan_id"))
            else:
                logger.info(f"Renewing subscription for user {order_data.get('user_id')} with plan {order_data.get('plan_id')}")
                await self.userdb.renew_subscription(order_data.get("user_id"), order_data.get("plan_id"))
            await self.order_code_cache.put_order_code(order_code, {
                "user_id": order_data.get("user_id"),
                "plan_id": order_data.get("plan_id"),
                "created_at": order_data.get("created_at"),
                "is_finished": True
            })
            await send(embed)
            return {"success": True}
        else:
            logger.info(f"Payment failed for order: {order_code} - Failling to manual verify")
            order_data = await self.order_code_cache.get_order_code(order_code)
            if order_data:
                embed = await build_fail_transaction_embed(
                    user_id=order_data.get("user_id"),
                    plan_id=order_data.get("plan_id")
                )
                await send(embed)
                await self.order_code_cache.delete_order_code(order_code)
            else:
                logger.warning(f"Order code {order_code} not found when trying to delete after failed payment")
            return {"success": False, "message": "Payment failed or cancelled"}

    async def get_all_pending_payment(self, request: GetAllPaymentsRequest) -> JSONResponse:
        ADMIN_REQUEST_KEY = request.admin_key

        if not ADMIN_REQUEST_KEY:
            return JSONResponse(
                content={"detail": "Admin key is required for this action!"},
                status_code=401
            )

        if ADMIN_REQUEST_KEY != ADMIN_KEY: 
            return JSONResponse(
                content={"detail": "Invalid admin key, access denied!"},
                status_code=403
            )

        pending_payments = []
        for order_code in await self.order_code_cache.get_all_order_codes():
            order_data = await self.order_code_cache.get_order_code(order_code)
            if order_data and not order_data.get("is_finished"):
                pending_payments.append({
                    "order_code": order_code,
                    "user_id": order_data.get("user_id"),
                    "plan_id": order_data.get("plan_id"),
                    "created_at": order_data.get("created_at")
                })

        if not pending_payments:
            return JSONResponse(
                content={"detail": "No pending payments found"},
                status_code=404
            )

        return JSONResponse(
            content={"pending_payments": pending_payments},
            status_code=200
        )
    
