# 运行与开发 / Running & Development

## 前置依赖

- Node.js `v22.22.0`，pnpm `11.2.2`
- Python `3.12`
- 本地 Redis 监听 `:6379`

## 一键启动

```bash
./start-dev.sh           # 后端(:8000) + 前端(:5777)
./start-dev.sh --seed    # 先灌入演示数据（本体 + 知识库 + RAG 工作流），再启动
```

脚本会：首次运行时创建 Python venv 并安装前后端依赖、检查 Redis、拉起两个服务，Ctrl-C 时一并关闭。

## 后端（手动）

```bash
cd server
./start.sh               # venv + 依赖 + 检查 Redis + uvicorn(reload)
# 或完全手动：
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

服务地址 `http://localhost:8000`（`/health`、`/docs`、`/openapi.json`）。灌演示本体：`cd server && ./seed.sh`。

## 前端（手动）

```bash
pnpm install
pnpm dev:ele             # 开发服务 http://localhost:5777
```

开发服务把 `/api` 代理到 `http://localhost:8000`（见 `apps/web-ele/vite.config.ts`）。

## 构建 / 校验

```bash
pnpm build:ele
pnpm typecheck
pnpm lint
```

## CLI

`agentscope-admin` 在终端操作平台。源码 checkout 下可直接 `./server/agentscope-admin …`，或 `cd server && pip install -e .` 安装控制台脚本。

```bash
agentscope-admin serve --reload                      # 启动后端
agentscope-admin seed                                # 演示本体 + 知识库 + 工作流
agentscope-admin agents list
agentscope-admin knowledge retrieve <kb_id> "可疑交易上报阈值"
agentscope-admin workflow run <workflow_id> --input query="电汇要上报吗"
agentscope-admin publish list
agentscope-admin keys create <app_id> --name ci-key
```

全局参数：`--base-url`（env `AGENTSCOPE_ADMIN_BASE_URL`，默认 `http://localhost:8000`）、`--user`（env `AGENTSCOPE_ADMIN_USER`，默认 `admin`）、`--json`。管理类命令需要后端**已在运行**。

## 配置 LLM 凭证

平台默认演示对接 **DeepSeek**（兼容 OpenAI 接口）。在「凭证」页或通过 `POST /credential/` 添加你的厂商 Key 后，在智能体「模型配置」里选择默认模型即可。

> 仓库与本包内**不含**任何真实 API Key（已校验）；前端 `.env` 中的 `VITE_APP_STORE_SECURE_KEY` 仅为占位符，请替换为你自己的值。

## 本 wiki 的再生成

```bash
cd server && source .venv/bin/activate && pip install markdown pygments
python ../wiki/build_wiki.py        # 重新由 wiki/content/*.md 渲染出静态 HTML
```
