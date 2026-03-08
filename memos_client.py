"""
Memos API v1 客户端封装
用法：
    client = MemosClient(url="https://memos.example.com", token="your_token")
    memo = await client.create("内容", "PRIVATE")
    memos = await client.list(page=1, page_size=5)
"""
import aiohttp


class MemosAPIError(Exception):
    """Memos API 请求异常"""

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"HTTP {status}: {message}")


class MemosClient:
    """Memos API v1 封装，所有方法均为异步"""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str):
        self._session = session
        self._base = url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self._timeout = aiohttp.ClientTimeout(total=10)

    # ── 内部辅助 ────────────────────────────────────────────────────────────

    def _memo_name(self, uid: str) -> str:
        """将 uid 转为 API name，如 me6k3pox → memos/me6k3pox"""
        if uid.startswith("memos/"):
            return uid
        return f"memos/{uid}"

    async def _request(self, method: str, path: str, **kwargs) -> dict | list | None:
        url = f"{self._base}/api/v1{path}"
        async with self._session.request(
            method, url, headers=self._headers, timeout=self._timeout, **kwargs
        ) as resp:
            if resp.status in (200, 204):
                if resp.content_length == 0 or resp.status == 204:
                    return None
                return await resp.json()
            error_text = await resp.text()
            raise MemosAPIError(resp.status, error_text)

    # ── 公开方法 ────────────────────────────────────────────────────────────

    async def create(self, content: str, visibility: str) -> dict:
        """创建笔记，返回笔记对象"""
        return await self._request(
            "POST", "/memos",
            json={"content": content, "visibility": visibility},
        )

    async def list(self, page: int = 1, page_size: int = 5) -> list[dict]:
        """
        获取笔记列表（按创建时间降序），page 从 1 开始。
        使用 pageToken 链式翻页，仅拉取必要数据。
        """
        page_token: str | None = None
        memos: list[dict] = []
        for current in range(page):
            params: dict = {"pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token
            data = await self._request("GET", "/memos", params=params)
            if not data:
                return []
            memos = data.get("memos", [])
            page_token = data.get("nextPageToken")
            if not page_token and current < page - 1:
                # 已无更多页，提前返回空
                return []
        return memos

    async def get(self, uid: str) -> dict:
        """查看笔记详情"""
        name = self._memo_name(uid)
        return await self._request("GET", f"/{name}")

    async def update(self, uid: str, content: str) -> dict:
        """编辑笔记内容"""
        name = self._memo_name(uid)
        return await self._request(
            "PATCH", f"/{name}",
            json={"content": content, "updateMask": "content"},
        )

    async def update_visibility(self, uid: str, visibility: str) -> dict:
        """修改笔记可见性"""
        name = self._memo_name(uid)
        return await self._request(
            "PATCH", f"/{name}",
            json={"visibility": visibility, "updateMask": "visibility"},
        )

    async def delete(self, uid: str) -> None:
        """删除笔记"""
        name = self._memo_name(uid)
        await self._request("DELETE", f"/{name}")

    async def search(self, keyword: str, limit: int = 10) -> list[dict]:
        """按内容关键词搜索笔记"""
        params = {
            "pageSize": limit,
            "filter": f'content.contains("{keyword}")',
        }
        data = await self._request("GET", "/memos", params=params)
        return data.get("memos", []) if data else []
