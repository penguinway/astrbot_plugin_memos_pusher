# AstrBot Memos 插件

快速将灵感推送到 [Memos](https://usememos.com)。

## 功能

- `/memo <内容>` — 将灵感记录到 Memos，默认私密可见

## 配置

在 AstrBot WebUI 插件管理中配置：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| memos_url | Memos 服务地址 | `https://memos.example.com` |
| memos_token | Access Token | 在 Memos 设置 → Access Tokens 中生成 |
| default_visibility | 默认可见性 | `PRIVATE` / `PROTECTED` / `PUBLIC` |

## 使用示例

```
/memo 今天想到一个好点子：用 AI 自动整理会议纪要
```

回复：
```
✅ 灵感已记录！
🔗 https://memos.example.com/m/xxxxx
```
