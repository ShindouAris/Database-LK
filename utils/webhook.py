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
    embed.set_footer(text="Locket Pro")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1280000000000000000/1280000000000000000/locketpro.png")
    return embed

async def send(embed: Embed):
    async with ClientSession() as session:
        webhook = Webhook.from_url(WEBHOOK_URL, session=session)
        await webhook.send(embed=embed)

