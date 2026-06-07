# 发布与集成 / Publishing & Integration

Dify 风格的「发布」：把一个智能体冻结成一个公开 **App**，一个 `token` 暴露三种集成方式，并配套 API Key 管理。后端 `app/publish/`，前端 `publish/`（发布管理）+ `webapp/`（公开 WebApp 页）。

- 模型：`PublishedApp`（token、运行配置快照、开场白/建议问题、`allowed_origins`、`rate_limit_per_min`）+ `AppApiKey`（SHA-256 哈希，仅创建时明文一次）。

## 三种集成方式

### 1. Web App（托管 UI）
- 地址：`/app/{token}`（公开页 `GET /public/apps/{token}` 取元信息，`POST /public/apps/{token}/chat` 流式对话）。
- 免登录，可配应用名/图标/开场白/建议问题。

### 2. REST API（接口）
- `POST /v1/apps/{token}/chat-messages`，Bearer（API Key）鉴权，支持流式(SSE)与阻塞(JSON)。
- API Key：仅创建时显示一次、存哈希、可吊销、记录最近使用。

### 3. 嵌入（Embed）
- `<iframe>` 内嵌 + 浮动聊天气泡 `<script>`（后端 `/static/embed.js`），一键复制粘到任意网站。

## 跨端支持（Cross-platform）

发布的应用一套代码适配多端，无需为每个终端单独开发：

- **响应式 WebApp**（`webapp/`）：使用动态视口高度 `100dvh` 避免移动端浏览器工具栏遮挡输入框；底部输入区适配刘海屏 / home indicator 安全区（`env(safe-area-inset-bottom)`）；头部 / 消息 / 输入区在手机 / 平板 / 桌面下采用不同间距。
- **可嵌入气泡**（`/static/embed.js`）：纯原生、无第三方依赖；图标为内联 lucide SVG（非 emoji）。桌面端为右下角浮动面板（默认 400×640，可配 `width` / `height`），手机端（`max-width: 640px`）自动切换为全屏，关闭按钮移至顶部，便于单手操作。
- **嵌入配置**：`window.AGENTSCOPE_APP = { url, color?, width?, height?, title? }`；`<iframe>` 片段带 `title` 与 `allowfullscreen`。

## 管理端点

| 操作 | 端点 |
| --- | --- |
| 发布/列表 | `POST/GET /admin/published-apps/` |
| 详情/改/删 | `GET/PATCH/DELETE /admin/published-apps/{app_id}` |
| Key 列表/创建 | `GET/POST /admin/published-apps/{app_id}/keys` |
| 吊销 Key | `POST /admin/published-apps/{app_id}/keys/{key_id}/revoke` |

## 配套能力

- **配置快照**：发布时冻结 model / 参数 / permission_mode，保证线上稳定，不随智能体后续改动而变。
- **访问控制**：`allowed_origins`（嵌入 CORS）、`rate_limit_per_min` 限流。
- **一键复制**：URL、curl 示例、iframe/script 片段（见集成中心页 `integration/`）。

## cURL 示例

```bash
curl -N https://YOUR_HOST/v1/apps/{token}/chat-messages \
  -H "Authorization: Bearer {api_key}" \
  -H "Content-Type: application/json" \
  -d '{"query":"你好","stream":true}'
```
