# AgentScope Admin · 项目 Wiki（静态站点）

这是基于整个代码库生成的一套**静态 wiki 站点**（HTML + markdown），可**离线**直接用浏览器打开，无需启动任何服务。

## 如何查看

直接双击或在浏览器打开：

```
wiki/index.html
```

左侧侧边栏在各页面间导航，覆盖：架构 / 数据模型 / 本体与语义层 / 智能体 / 工作流 / 知识库 / 多智能体编排 / 发布 / 平台服务 / API 参考 / 二次开发指南 / 路线图 / 运行与开发。

## 目录结构

```
wiki/
├── index.html            # 入口（= 概览页）
├── 01-overview.html …    # 各页面（预渲染的静态 HTML）
├── content/*.md          # 各页面的 markdown 源
├── assets/style.css      # 样式
└── build_wiki.py         # 由 content/*.md 重新生成 HTML 的脚本
```

## 重新生成

修改 `content/*.md` 后重新渲染：

```bash
cd server && source .venv/bin/activate && pip install markdown pygments
python ../wiki/build_wiki.py
```
