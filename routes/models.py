from pydantic import BaseModel


class TimelinesResponse(BaseModel):
    id: int
    date: str
    title: str
    description: str

class UserInfo(BaseModel):
    plan: str
    username: str
    displayName: str
    profilePicture: str

class Stats(BaseModel):
    hearts: int
    shares: int
    comments: int
    downloads: int

class Options(BaseModel):
    type: str
    caption: str
    color_top: str
    color_text: str
    color_bottom: str

class CaptionsResponse(BaseModel):
    id: int
    uid: str
    options: Options
    user_info: UserInfo
    stats: Stats
    created_at: str

class DonatorsResponse(BaseModel):
    id: str
    donorname: str
    amount: int
    date: str
    message: str
    created_at: str

class ThemesResponse(BaseModel):
    id: str
    preset_id: str
    type: str
    icon: str
    preset_caption: str
    color_top: str
    color_bottom: str
    text_color: str
    created_at: str
    order_index: int

class Notification(BaseModel):
    id: int
    message: str
    created_at: str

class NotificationResponse(BaseModel):
    notifications: list[Notification]