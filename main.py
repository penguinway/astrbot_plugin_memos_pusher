from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import aiohttp


@register(
    "astrbot_plugin_memos_pusher",
    "penguinway",
    "快速将灵感推送到 Memos",
    "1.0.0",
)
class MemosPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    def _get_url(self) -> str:
        url = self.config.get("memos_url", "").strip().rstrip("/")
        return url

    def _get_token(self) -> str:
        return self.config.get("memos_token", "").strip()

    def _get_visibility(self) -> str:
        return self.config.get("default_visibility", "PRIVATE")

    @filter.command("memo")
    async def memo(self, event: AstrMessageEvent):
        """将灵感推送到 Memos。用法: /memo <内容>"""
        content = event.message_str.strip()
        if not content:
            yield event.plain_result("❌ 请输入内容，用法: /memo <你的灵感>")
            return

        url = self._get_url()
        token = self._get_token()

        if not url or not token:
            yield event.plain_result("❌ 请先在插件配置中设置 Memos 地址和 Token")
            return

        api_url = f"{url}/api/v1/memos"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "content": content,
            "visibility": self._get_visibility(),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        memo_name = data.get("name", "")
                        # Extract memo uid for link
                        memo_uid = data.get("uid", "")
                        link = f"{url}/m/{memo_uid}" if memo_uid else url
                        yield event.plain_result(
                            f"✅ 灵感已记录！\n🔗 {link}"
                        )
                    else:
                        error_text = await resp.text()
                        logger.error(f"Memos API error: {resp.status} {error_text}")
                        yield event.plain_result(
                            f"❌ 推送失败 (HTTP {resp.status})"
                        )
        except aiohttp.ClientError as e:
            logger.error(f"Memos connection error: {e}")
            yield event.plain_result(f"❌ 连接 Memos 失败，请检查地址配置")
        except Exception as e:
            logger.error(f"Memos unexpected error: {e}")
            yield event.plain_result(f"❌ 发生错误: {e}")

    async def terminate(self):
        pass
