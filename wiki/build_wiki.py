#!/usr/bin/env python3
"""Render the static wiki site from ``wiki/content/*.md`` into standalone HTML.

The output is a fully static site (HTML + CSS, no runtime/JS dependency for
rendering) that opens offline via ``file://`` — just open ``wiki/index.html``.

Regenerate with::

    cd server && source .venv/bin/activate && pip install markdown pygments
    python ../wiki/build_wiki.py
"""

from __future__ import annotations

import re
from pathlib import Path

import markdown

WIKI_DIR = Path(__file__).resolve().parent
CONTENT_DIR = WIKI_DIR / "content"

# Ordered navigation: (markdown filename, sidebar group, sidebar label).
NAV: list[tuple[str, str, str]] = [
    ("01-overview.md", "入门", "概览 Overview"),
    ("02-architecture.md", "入门", "架构 Architecture"),
    ("03-data-model.md", "入门", "数据模型 Data Model"),
    ("04-ontology.md", "核心能力", "本体与语义层 Ontology"),
    ("05-agents.md", "核心能力", "智能体与模型配置 Agents"),
    ("06-workflow.md", "核心能力", "工作流编排 Workflow"),
    ("07-knowledge.md", "核心能力", "知识库与流水线 Knowledge"),
    ("08-orchestration.md", "核心能力", "多智能体编排 Orchestration"),
    ("09-publish.md", "核心能力", "发布与集成 Publishing"),
    ("10-platform-services.md", "核心能力", "平台服务 Platform Services"),
    ("11-api-reference.md", "参考", "API 参考 API Reference"),
    ("12-developer-guide.md", "参考", "二次开发指南 Developer Guide"),
    ("13-roadmap.md", "参考", "路线图与缺口 Roadmap"),
    ("14-running.md", "参考", "运行与开发 Running"),
]

PAGE_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · AgentScope Admin Wiki</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="brand">
    <div class="logo">AS</div>
    <div>
      <div class="title">AgentScope Admin</div>
      <div class="subtitle">项目 Wiki（静态）</div>
    </div>
  </div>
  <nav class="nav">
{nav}
  </nav>
</aside>
<main class="content">
{body}
<div class="page-footer">
  <span>AgentScope Admin · 静态 Wiki</span>
  <span>{prevnext}</span>
</div>
</main>
</div>
</body>
</html>
"""


def html_name(md_name: str) -> str:
    return md_name.replace(".md", ".html")


def build_nav(active: str) -> str:
    lines: list[str] = []
    current_group = None
    for md_name, group, label in NAV:
        if group != current_group:
            lines.append(f'    <div class="nav-group-label">{group}</div>')
            current_group = group
        cls = ' class="active"' if md_name == active else ""
        lines.append(f'    <a href="{html_name(md_name)}"{cls}>{label}</a>')
    return "\n".join(lines)


def prev_next(idx: int) -> str:
    parts: list[str] = []
    if idx > 0:
        prev = NAV[idx - 1]
        parts.append(f'← <a href="{html_name(prev[0])}">{prev[2]}</a>')
    if idx < len(NAV) - 1:
        nxt = NAV[idx + 1]
        parts.append(f'<a href="{html_name(nxt[0])}">{nxt[2]}</a> →')
    return " &nbsp;|&nbsp; ".join(parts)


def fix_links(body: str) -> str:
    # Internal cross-links in markdown were authored as ``foo.html`` already;
    # ensure any ``.md`` links also resolve to ``.html``.
    return re.sub(r'href="([0-9][^"]*?)\.md([^"]*)"', r'href="\1.html\2"', body)


def main() -> None:
    md = markdown.Markdown(
        extensions=["fenced_code", "tables", "toc", "codehilite", "attr_list"],
        extension_configs={
            "codehilite": {"guess_lang": False, "noclasses": False},
            "toc": {"title": "本页目录"},
        },
    )
    built = 0
    for idx, (md_name, _group, label) in enumerate(NAV):
        src = CONTENT_DIR / md_name
        text = src.read_text(encoding="utf-8")
        md.reset()
        body = fix_links(md.convert(text))
        page = PAGE_TEMPLATE.format(
            title=label,
            nav=build_nav(md_name),
            body=body,
            prevnext=prev_next(idx),
        )
        (WIKI_DIR / html_name(md_name)).write_text(page, encoding="utf-8")
        built += 1

    # index.html mirrors the first page.
    first_html = html_name(NAV[0][0])
    (WIKI_DIR / "index.html").write_text(
        (WIKI_DIR / first_html).read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"built {built} pages + index.html into {WIKI_DIR}")


if __name__ == "__main__":
    main()
