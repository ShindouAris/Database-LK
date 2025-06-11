from payos import PaymentData, PayOS, ItemData
from os import environ
from fastapi import HTTPException
from json import loads
from datetime import datetime, timezone
from logging import getLogger

PAYOS_CLIENT_ID = str(environ.get("PAYOS_CLIENT_ID"))
PAYOS_API_KEY = str(environ.get("PAYOS_API_KEY"))
PAYOS_CHECKSUM_KEY = str(environ.get("PAYOS_CHECKSUM_KEY"))
PAYOS_CONFIRM_WEBHOOK = str(environ.get("PAYOS_CONFIRM_WEBHOOK"))

class Payment(PayOS):
    def __init__(self) -> None:
        super().__init__(PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY)
        self.confirmWebhook = PAYOS_CONFIRM_WEBHOOK
        self.logger = getLogger(__name__)
    
    def choose_items(self, plan_id: str) -> ItemData | None:
        match plan_id:
            case "premium_lite":
                return ItemData(
                    name="Premium Lite",
                    price=10000,
                    quantity=1,
                )
            case "premium":
                return ItemData(
                    name="Premium",
                    price=17000,
                    quantity=1,
                )
            case "pro_plus":
                return ItemData(
                    name="Pro Plus",
                    price=30000,
                    quantity=1,
                )
            case _:
                return None
    
    def create(self, items: ItemData, amount: int) -> dict:
        try:
            payment_data = PaymentData(orderCode=int(datetime.now(timezone.utc).timestamp()), items=[items], description="Mua gói trên web", cancelUrl="/", returnUrl="/", amount=amount)
            payosCreatePayment = self.createPaymentLink(payment_data)

            return {
                "qr_code": payosCreatePayment.qrCode,
                "order_code": payosCreatePayment.orderCode
            }
        except Exception as e:
            self.logger.error(f"Error creating payment: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def cancel(self, order_code: str):
        try:
            self.logger.info(f"Cancelling payment: {order_code}")
            payosCancelPayment = self.cancelPaymentLink(order_code)
            return payosCancelPayment.status
        except Exception as e:
            self.logger.error(f"Error canceling payment: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        
    def verify_webhook(self, webhook_data):
        try:
            payosVerifyPayment = self.verifyPaymentWebhookData(webhook_data)
            return payosVerifyPayment.desc
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    def check_payment_status(self, webhook_raw_body):
        self.logger.info(f"Checking payment status for order code: {webhook_raw_body.get('orderCode')}")
        return webhook_raw_body.get("success") == True
    
    

