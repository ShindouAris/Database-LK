from payos import PaymentData, PayOS
from os import environ
from fastapi import HTTPException
from json import loads
from datetime import datetime, timezone

PAYOS_CLIENT_ID = str(environ.get("PAYOS_CLIENT_ID"))
PAYOS_API_KEY = str(environ.get("PAYOS_API_KEY"))
PAYOS_CHECKSUM_KEY = str(environ.get("PAYOS_CHECKSUM_KEY"))
PAYOS_CONFIRM_WEBHOOK = str(environ.get("PAYOS_CONFIRM_WEBHOOK"))

class Payment(PayOS):
    def __init__(self) -> None:
        super().__init__(PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY)
        self.confirmWebhook = PAYOS_CONFIRM_WEBHOOK

    def create(self, user_id: str, amount: int) -> dict:
        try:
            payment_data = PaymentData(orderCode=int(datetime.now(timezone.utc).timestamp()), amount=amount, description=user_id, cancelUrl="/", returnUrl="/")
            payosCreatePayment = self.createPaymentLink(payment_data)

            return {
                "qr_code": payosCreatePayment.qrCode,
                "order_code": payosCreatePayment.orderCode
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    def cancel(self, order_code: str):
        try:
            payosCancelPayment = self.cancelPaymentLink(order_code)
            return payosCancelPayment.status
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    def verify_webhook(self, webhook_data):
        try:
            payosVerifyPayment = self.verifyPaymentWebhookData(webhook_data)
            return payosVerifyPayment.desc
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    def check_payment_status(self, webhook_raw_body):
        return webhook_raw_body.get("success") == True
    
    

