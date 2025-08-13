from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from logging import getLogger
from utils.logger import LOGGING_CONFIG
from routes.global_db import LocketProRouter
from routes.subscription_route import SubscriptionRoute
from routes.utils import UtilsRouter
import datetime
from dotenv import load_dotenv
import os

load_dotenv()
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", ["*"])
logger = getLogger(__name__)

class LocketUploaderDB(FastAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(docs_url=None, redoc_url=None, openapi_url=None, swagger_ui_oauth2_redirect_url=None, *args, **kwargs)
        self.add_middleware(
            CORSMiddleware,
            allow_origins=ALLOWED_ORIGINS,
            allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
            allow_credentials=True,
        )
        self.uptime = datetime.datetime.now(datetime.timezone.utc).timestamp()
        self.include_router(LocketProRouter())
        self.include_router(SubscriptionRoute())
        self.include_router(UtilsRouter())
        self.add_api_route("/status", self.get_status, methods=["GET", "HEAD"])
    
    async def get_status(self):
        return {
            "status": "ok",
            "uptime": self.uptime,
            "version": "kanade-v3"
        }


if __name__ == "__main__":
    import uvicorn
    app = LocketUploaderDB()
    uvicorn.run(app, host="0.0.0.0", port=5004, log_config=LOGGING_CONFIG)