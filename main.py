from __future__ import annotations

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger, AstrBotConfig
import aiohttp

from .memos_client import MemosClient, MemosAPIError

_VISIBILITY_OPTIONS = ("PRIVATE", "PROTECTED", "PUBLIC")

_HELP_TEXT = """📝 Memos 插件命令帮助

创建笔记：
  /memo <内容>

管理笔记（/memos <子命令>）：
  list [页码]          列出笔记（每页5条，默认第1页）
  view <uid>           查看笔记完整内容
  del <uid>            删除笔记
  search <关键词>      按内容搜索笔记
  vis <uid> <可见性>   修改可见性（PRIVATE/PROTECTED/PUBLIC）
  edit <uid> <内容>    编辑笔记内容
  help                 显示此帮助
""".strip()


class MemosPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        # 待确认删除：{session_key: uid}
        self._pending_del: dict[str, str] = {}

    @staticmethod
    def _strip_command(raw: str, cmd: str) -> str:
        """从消息文本中去除命令前缀，如 /memo、memo"""
        for prefix in (f"/{cmd}", cmd):
            if raw.lower().startswith(prefix):
                return raw[len(prefix):].strip()
        return raw.strip()

    # ── Session & 配置 ──────────────────────────────────────────────────────

    def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP Session（延迟初始化）"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _get_url(self) -> str:
        return self.config.get("memos_url", "").strip().rstrip("/")

    def _get_token(self) -> str:
        return self.config.get("memos_token", "").strip()

    def _get_visibility(self) -> str:
        return self.config.get("default_visibility", "PRIVATE")

    def _make_client(self) -> MemosClient | None:
        """构建 MemosClient，配置缺失时返回 None"""
        url, token = self._get_url(), self._get_token()
        if not url or not token:
            return None
        return MemosClient(self._get_session(), url, token)

    # ── 格式化工具 ──────────────────────────────────────────────────────────

    @staticmethod
    def _uid(memo: dict) -> str:
        """从 memo 对象提取 uid（name 字段形如 memos/xxxx）"""
        return memo.get("name", "").split("/")[-1] or memo.get("uid", "")

    @staticmethod
    def _excerpt(content: str, limit: int = 40) -> str:
        content = content.replace("\n", " ")
        return content[:limit] + "…" if len(content) > limit else content

    @staticmethod
    def _vis_emoji(vis: str) -> str:
        return {"PRIVATE": "🔒", "PROTECTED": "🔐", "PUBLIC": "🌐"}.get(vis, "❓")

    def _fmt_list(self, memos: list[dict], page: int) -> str:
        if not memos:
            return f"📭 第 {page} 页没有笔记"
        lines = [f"📋 笔记列表（第 {page} 页）\n"]
        for i, m in enumerate(memos, 1):
            uid = self._uid(m)
            vis = self._vis_emoji(m.get("visibility", ""))
            excerpt = self._excerpt(m.get("content", ""))
            lines.append(f"{i}. {vis} [{uid}]\n   {excerpt}")
        return "\n".join(lines)

    def _fmt_memo(self, m: dict) -> str:
        uid = self._uid(m)
        vis = m.get("visibility", "PRIVATE")
        content = m.get("content", "")
        create_time = m.get("createTime", "")[:10]
        return (
            f"📄 笔记详情\n"
            f"uid：{uid}\n"
            f"可见性：{self._vis_emoji(vis)} {vis}\n"
            f"创建：{create_time}\n"
            f"──────────────\n"
            f"{content}"
        )

    # ── /memo 命令（创建） ───────────────────────────────────────────────────

    @filter.command("memo")
    async def memo(self, event: AstrMessageEvent):
        """将灵感推送到 Memos。用法: /memo <内容>"""
        content = self._strip_command(event.message_str, "memo")

        if not content:
            yield event.plain_result("❌ 请输入内容，用法: /memo <你的灵感>")
            return

        client = self._make_client()
        if client is None:
            yield event.plain_result("❌ 请先在插件配置中设置 Memos 地址和 Token")
            return

        try:
            data = await client.create(content, self._get_visibility())
            uid = self._uid(data)
            link = f"{self._get_url()}/m/{uid}" if uid else self._get_url()
            yield event.plain_result(f"✅ 灵感已记录！\n🔗 {link}")
        except MemosAPIError as e:
            logger.error(f"Memos API error: {e}")
            yield event.plain_result(f"❌ 推送失败 (HTTP {e.status})")
        except aiohttp.ClientError as e:
            logger.error(f"Memos connection error: {e}")
            yield event.plain_result("❌ 连接 Memos 失败，请检查地址配置")
        except Exception as e:
            logger.error(f"Memos unexpected error: {e}")
            yield event.plain_result(f"❌ 发生错误: {e}")

    # ── /memos 命令（管理路由） ──────────────────────────────────────────────

    @filter.command("memos")
    async def memos(self, event: AstrMessageEvent):
        """Memos 笔记管理。用法: /memos <子命令> [参数]"""
        args = self._strip_command(event.message_str, "memos").split(maxsplit=1)

        if not args or args[0] == "help":
            yield event.plain_result(_HELP_TEXT)
            return

        client = self._make_client()
        if client is None:
            yield event.plain_result("❌ 请先在插件配置中设置 Memos 地址和 Token")
            return

        subcmd = args[0].lower()
        rest = args[1] if len(args) > 1 else ""

        # del 需要 session_key 参与确认流程，单独处理
        if subcmd == "del":
            try:
                result = await self._handle_del(rest, event.unified_msg_origin)
                yield event.plain_result(result)
            except Exception as e:
                logger.error(f"Memos del error: {e}")
                yield event.plain_result(f"❌ 发生错误: {e}")
            return

        handlers = {
            "list": self._handle_list,
            "view": self._handle_view,
            "search": self._handle_search,
            "vis": self._handle_vis,
            "edit": self._handle_edit,
        }

        handler = handlers.get(subcmd)
        if handler is None:
            yield event.plain_result(f"❌ 未知子命令「{subcmd}」，发送 /memos help 查看帮助")
            return

        try:
            result = await handler(client, rest)
            yield event.plain_result(result)
        except MemosAPIError as e:
            logger.error(f"Memos API error [{subcmd}]: {e}")
            yield event.plain_result(f"❌ 操作失败 (HTTP {e.status})")
        except aiohttp.ClientError as e:
            logger.error(f"Memos connection error [{subcmd}]: {e}")
            yield event.plain_result("❌ 连接 Memos 失败，请检查地址配置")
        except Exception as e:
            logger.error(f"Memos unexpected error [{subcmd}]: {e}")
            yield event.plain_result(f"❌ 发生错误: {e}")

    # ── 子命令处理器 ─────────────────────────────────────────────────────────

    async def _handle_list(self, client: MemosClient, rest: str) -> str:
        page = 1
        if rest.strip().isdigit():
            page = max(1, int(rest.strip()))
        memos = await client.list(page=page, page_size=5)
        return self._fmt_list(memos, page)

    async def _handle_view(self, client: MemosClient, rest: str) -> str:
        uid = rest.strip()
        if not uid:
            return "❌ 用法: /memos view <uid>"
        memo = await client.get(uid)
        return self._fmt_memo(memo)

    async def _handle_del(self, rest: str, session_key: str) -> str:
        uid = rest.strip()
        if not uid:
            return "❌ 用法: /memos del <uid>"
        self._pending_del[session_key] = uid
        return f"⚠️ 确认删除笔记 [{uid}]？\n回复「确认」执行删除，「取消」放弃"

    async def _handle_search(self, client: MemosClient, rest: str) -> str:
        keyword = rest.strip()
        if not keyword:
            return "❌ 用法: /memos search <关键词>"
        memos = await client.search(keyword)
        if not memos:
            return f"🔍 未找到包含「{keyword}」的笔记"
        lines = [f"🔍 搜索「{keyword}」，共 {len(memos)} 条：\n"]
        for i, m in enumerate(memos, 1):
            uid = self._uid(m)
            vis = self._vis_emoji(m.get("visibility", ""))
            excerpt = self._excerpt(m.get("content", ""))
            lines.append(f"{i}. {vis} [{uid}]\n   {excerpt}")
        return "\n".join(lines)

    async def _handle_vis(self, client: MemosClient, rest: str) -> str:
        parts = rest.strip().split(maxsplit=1)
        if len(parts) != 2:
            return "❌ 用法: /memos vis <uid> <PRIVATE|PROTECTED|PUBLIC>"
        uid, vis = parts[0], parts[1].upper()
        if vis not in _VISIBILITY_OPTIONS:
            return f"❌ 可见性必须是 PRIVATE / PROTECTED / PUBLIC"
        await client.update_visibility(uid, vis)
        return f"✅ 笔记 [{uid}] 可见性已设为 {self._vis_emoji(vis)} {vis}"

    async def _handle_edit(self, client: MemosClient, rest: str) -> str:
        parts = rest.strip().split(maxsplit=1)
        if len(parts) != 2:
            return "❌ 用法: /memos edit <uid> <新内容>"
        uid, new_content = parts[0], parts[1]
        await client.update(uid, new_content)
        return f"✅ 笔记 [{uid}] 已更新"

    # ── 删除确认交互 ─────────────────────────────────────────────────────────

    @filter.regex(r"^(确认|取消)$")
    async def confirm_delete(self, event: AstrMessageEvent):
        """处理删除操作的二次确认"""
        session_key = event.unified_msg_origin
        uid = self._pending_del.get(session_key)
        if uid is None:
            # 无待确认操作，不干预
            return

        text = event.message_str.strip()
        del self._pending_del[session_key]

        if text == "取消":
            yield event.plain_result(f"↩️ 已取消删除笔记 [{uid}]")
            return

        # 确认 → 执行删除
        client = self._make_client()
        if client is None:
            yield event.plain_result("❌ 配置缺失，无法执行删除")
            return

        try:
            await client.delete(uid)
            yield event.plain_result(f"🗑️ 笔记 [{uid}] 已删除")
        except MemosAPIError as e:
            logger.error(f"Memos del confirmed error: {e}")
            yield event.plain_result(f"❌ 删除失败 (HTTP {e.status})")
        except Exception as e:
            logger.error(f"Memos del unexpected error: {e}")
            yield event.plain_result(f"❌ 发生错误: {e}")

    # ── 生命周期 ─────────────────────────────────────────────────────────────

    async def terminate(self):
        """插件终止时关闭 HTTP Session"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Memos plugin HTTP session closed")
