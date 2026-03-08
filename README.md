# AstrBot Memos 插件

在 AstrBot 中完整管理你的 [Memos](https://usememos.com) 笔记。

## 功能

- **创建笔记** — `/memo <内容>`
- **列出笔记** — `/memos list [页码]`
- **查看详情** — `/memos view <uid>`
- **删除笔记** — `/memos del <uid>`（含二次确认）
- **搜索笔记** — `/memos search <关键词>`
- **修改可见性** — `/memos vis <uid> <PRIVATE|PROTECTED|PUBLIC>`
- **编辑内容** — `/memos edit <uid> <新内容>`
- **查看帮助** — `/memos help`

## 配置

在 AstrBot WebUI 插件管理中配置：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| memos_url | Memos 服务地址 | `https://memos.example.com` |
| memos_token | Access Token | 在 Memos 设置 → Access Tokens 中生成 |
| default_visibility | 默认可见性 | `PRIVATE` / `PROTECTED` / `PUBLIC` |

## 使用示例

**创建笔记**
```
/memo 今天想到一个好点子：用 AI 自动整理会议纪要
```
```
✅ 灵感已记录！
🔗 https://memos.example.com/m/me6k3pox
```

**列出笔记**
```
/memos list
```
```
📋 笔记列表（第 1 页）

1. 🔒 [me6k3pox]
   今天想到一个好点子：用 AI 自动整理会议纪要
2. 🌐 [ab1c2d3e]
   读书笔记：深度学习基础
```

**删除笔记（二次确认）**
```
/memos del me6k3pox
```
```
⚠️ 确认删除笔记 [me6k3pox]？
回复「确认」执行删除，「取消」放弃
```
```
确认
```
```
🗑️ 笔记 [me6k3pox] 已删除
```

## 要求

- AstrBot 最新版
- Memos v0.22+（搜索功能依赖 `content.contains()` filter）
