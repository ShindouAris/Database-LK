default_plans = [
    {
        "id": "free",
        "name": "Free",
        "price": 0,
        "duration_days": 0,
        "max_uploads": 999999,
        "perks": {
            "Đăng không giới hạn ảnh/video": True,
            "Tuỳ chỉnh nền và trang trí đầy đủ": True,
            "Hỗ trợ tuỳ chỉnh nâng cao": True,
            "Toàn quyền tuỳ chỉnh mọi tính năng": True,
            "Giới hạn upload ảnh 3MB": True,
            "Giới hạn upload video 7MB": True,
        },
        "max_image_size": 3,
        "max_video_size": 7,
        "has_ads": True,
        "priority_support": False
    },
    {
        "id": "premium_lite",
        "name": "Premium Lite",
        "price": 10000,
        "duration_days": 30,
        "max_uploads": 999999,
        "perks": {
            "Mọi tính năng của gói Free": True,
            "Không có quảng cáo": True,
            "Giới hạn upload ảnh 5MB": True,
            "Giới hạn upload video 10MB": True,
        },
        "max_image_size": 5,
        "max_video_size": 10,
        "has_ads": False,
        "priority_support": False
    },
    {
        "id": "premium",
        "name": "Premium",
        "price": 17000,
        "duration_days": 30,
        "max_uploads": 999999,
        "perks": {
            "Mọi tính năng của gói Premium Lite": True,
            "Không có quảng cáo": True,
            "Hỗ trợ ưu tiên": True,
            "Giới hạn upload ảnh 7MB": True,
            "Giới hạn upload video 20MB": True,
        },
        "max_image_size": 7,
        "max_video_size": 20,
        "has_ads": False,
        "priority_support": True
    },
    {
        "id": "pro_plus",
        "name": "Pro Plus",
        "price": 30000,
        "duration_days": 90,
        "max_uploads": 999999,
        "perks": {
            "Mọi tính năng của gói Premium": True,
            "Không có quảng cáo": True,
            "Hỗ trợ ưu tiên 24/7": True,
            "Tối đa giới hạn upload ảnh và video (10MB / 25MB)": True,
        },
        "max_image_size": 10,
        "max_video_size": 25,
        "has_ads": False,
        "priority_support": True
    }
]

def get_plan_by_id(plan_id: str) -> dict | None:
    for plan in default_plans:
        if plan["id"] == plan_id:
            return plan
    return None