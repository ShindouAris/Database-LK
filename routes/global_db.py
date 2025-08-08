from fastapi import APIRouter
from routes.models import TimelinesResponse, CaptionsResponse, DonatorsResponse, ThemesResponse, Options, UserInfo, Stats, Notification, NotificationResponse
from utils.read_data import get_captions_post, get_timelines, get_donators, get_themes, get_notifications
import aiohttp

class LocketProRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(prefix="/locketpro", *args, **kwargs)
        self.add_api_route("/user-themes/caption-posts", self.get_user_themes, methods=["GET"])
        self.add_api_route("/themes", self.get_themes, methods=["GET"])
        self.add_api_route("/timelines", self.get_timelines, methods=["GET"])
        self.add_api_route("/donations", self.get_donators, methods=["GET"])
        self.add_api_route("/notification", self.get_notifications, methods=["GET"])

    async def get_user_themes(self, next_token: str | None = None):
        data = get_captions_post()
        async with aiohttp.ClientSession() as client:
            data = await client.get(f"https://api.chisadin.site/api/get_captionV2{f'?next_token={next_token}' if next_token else ''}")
        return await data.json()

    async def get_themes(self):
        data = get_themes()
        list_data = []

        if data:
            for item in data:
                list_data.append(ThemesResponse(**item))
        return list_data
    
    async def get_timelines(self):
        data = get_timelines()
        list_data = []

        if data:
            for item in data:
                list_data.append(TimelinesResponse(**item))
        return list_data
    
    async def get_donators(self):
        data = get_donators()

        list_data = []

        if data:
            for item in data:
                list_data.append(DonatorsResponse(**item))
        return list_data
    
    async def get_notifications(self):
        data = get_notifications()

        return data or []
    