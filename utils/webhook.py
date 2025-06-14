from disnake import Webhook, Embed
from aiohttp import ClientSession
import os

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

async def build_transaction_embed(user_id: str, plan_id: str, amount: int) -> Embed:
    embed = Embed(
        title="Đơn chờ phê duyệt",
        description=f"Đã có đơn chờ phê duyệt.",
        color=0x00ff00
    )
    embed.add_field(name="UserID", value=user_id, inline=False)
    embed.add_field(name="PlanID", value=plan_id, inline=False)
    embed.add_field(name="Amount", value=amount, inline=False)
    embed.set_footer(text="Locket Kanade")
    return embed

async def build_fail_transaction_embed(user_id: str, plan_id: str) -> Embed:
    embed = Embed(
        title="Đơn thất bại",
        description=f"Đơn hàng của {user_id} đã thất bại.",
        color=0xff0000
    )
    embed.add_field(name="UserID", value=user_id, inline=False)
    embed.add_field(name="PlanID", value=plan_id, inline=False)
    embed.set_footer(text="Locket Kanade")
    return embed

async def build_success_transaction_embed(user_id: str, plan_id: str) -> Embed:
    embed = Embed(
        title="Đơn thành công",
        description=f"Đơn hàng của {user_id} đã thành công.",
        color=0x00ff00
    )
    embed.add_field(name="UserID", value=user_id, inline=False)
    embed.add_field(name="PlanID", value=plan_id, inline=False)
    return embed

async def send(embed: Embed):
    async with ClientSession() as session:
        webhook = Webhook.from_url(WEBHOOK_URL, session=session)
        await webhook.send(embed=embed)

