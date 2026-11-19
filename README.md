# AgentScope Admin

Admin console for the AgentScope platform.

## Demo mode

Start the mock admin API without Redis or a live AgentScope instance:

```bash
cd server
python -c "import uvicorn; from app.demo import app; uvicorn.run(app, host='127.0.0.1', port=8080)"
```

`GET /admin/status` returns a connection banner. The web console can show that banner when the real backend is down.

```bash
cd server && pytest tests/test_demo_mode.py
```

## Overview
Vue-based administration interface for managing AgentScope configurations, agents, workflows, and related settings.

## Features
- Agent and configuration management
- Dashboard interface
- Admin controls for AgentScope resources

## Tech Stack
- Vue.js
- Frontend admin dashboard

## Status
In development.

## Getting Started
```bash
# Typical Vue project setup
npm install
npm run dev
```

