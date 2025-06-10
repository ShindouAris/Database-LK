from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from logging import getLogger
from utils.logger import LOGGING_CONFIG
from routes.global_db import LocketProRouter
from routes.subscription_route import SubscriptionRoute
import datetime
from dotenv import load_dotenv

load_dotenv()

logger = getLogger(__name__)

class LocketUploaderDB(FastAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
        )
        self.uptime = datetime.datetime.now(datetime.timezone.utc).timestamp()
        self.include_router(LocketProRouter())
        self.include_router(SubscriptionRoute())
        self.add_api_route("/status", self.get_status, methods=["GET", "HEAD"])
    
    async def get_status(self):
        return {
            "status": "ok",
            "uptime": self.uptime,
            "version": "1.0.0"
        }


if __name__ == "__main__":
    import uvicorn
    app = LocketUploaderDB()
    uvicorn.run(app, host="0.0.0.0", port=5004, log_config=LOGGING_CONFIG)