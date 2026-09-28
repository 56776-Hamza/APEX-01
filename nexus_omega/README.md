# NEXUS-OMEGA (APEX-1)
### Autonomous Multi-Agent Cognitive Operating System

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 1. System Overview

**NEXUS-OMEGA (APEX-1)** is an unrestricted, 24/7 autonomous multi-agent cognitive operating system designed for unconstrained real-world execution. Unlike standard prompt-and-response chatbots, APEX-1 operates as an asynchronous, proactive multimodal swarm capable of self-directed goal execution, live code generation, continuous self-learning via scientific hypothesis testing, and multi-channel command dispatch.

```
+---------------------------------------------------------------------------------------------------+
|                                     UNIFIED APEX-1 ARCHITECTURE                                    |
+---------------------------------------------------------------------------------------------------+
|  INTERFACES: Telegram Bot | Web UI / Kanban | Voice/Vision (LiveKit) | Headless CLI               |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|  ORCHESTRATION & ROUTING CORE: Supervisor Router | Kanban State Engine | Dynamic Task Graph       |
+---------------------------------------------------------------------------------------------------+
         |                                        |                                        |
         v                                        v                                        v
+------------------+                    +--------------------+                   +------------------+
| Worker Swarm     |                    | Self-Learning Loop |                   | Tool Execution   |
| - Research Agent |                    | - Hypothesis Gen   |                   | - Bash Sandbox   |
| - Code Synthesizer                    | - 1-Variable Mutate|                   | - Live Web Duck  |
| - Security / Red |                    | - Ledger Reflection|                   | - Gmail / GCal   |
+------------------+                    +--------------------+                   +------------------+
         |                                        |                                        |
         +----------------------------------------+----------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|  MULTI-PROVIDER LLM ABSTRACTION: OpenRouter | Gemini Flash | Claude 3.5 | Ollama Offline          |
+---------------------------------------------------------------------------------------------------+
|  PERSISTENCE & SHARED MEMORY: PostgreSQL + pgvector | Redis Ephemeral State | File-Backed State   |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Core Capabilities

* **24/7 Autonomous Daemon:** Continuous worker loop that decomposes high-level goals into directed acyclic graphs (DAGs) and executes tasks through sequential dependencies (`TODO` → `READY` → `IN_PROGRESS` → `BLOCKED` / `DONE`).
* **Swarm Agent Personas:**
  * **Supervisor Router:** High-level directive intake & DAG decomposition.
  * **Red-Team Security (SecOps):** Vulnerability audits, recon, and sandbox validation.
  * **Code Synthesizer:** Script generation, deployment automation, and error self-correction.
  * **OSINT / Web Scraper:** Real-time web intelligence querying via DuckDuckGo.
  * **Market Quant:** Loss computation, Sharpe ratio benchmark tracking, and mathematical optimization.
* **Scientific Self-Improvement Loop:**
  * Tests outcomes against mathematical benchmark scoring: $S_{\text{composite}} = 0.4 \times C + 0.3 \times L + 0.3 \times \text{Sharpe}$.
  * Applies **single-variable mutations** per cycle (temperature, retry limit, search depth, scraper timeout, chunk size, backoff factor).
  * Automatically adopts mutations that beat historical median baselines and logs experiments to the parameter ledger.
* **Omni-Channel Dispatch:**
  1. **Kanban Web Dashboard:** Glassmorphic cybernetic UI with real-time WebSockets (`/ws/events`, `/ws/logs`), live agent reasoning stream, Quick Command bar, and evolution parameter ledger.
  2. **Telegram Bot:** Command listener (`/goal`, `/status`, `/resume`, `/kill`) and instant push notifications for `BLOCKED` tasks.
  3. **LiveKit WebRTC Audio/Vision:** Full-duplex voice streaming, interruption handling, and camera frame object detection.
  4. **Headless Terminal CLI (`cli.py`):** Interactive shell and standalone executor with ASCII matrix inspection.

---

## 3. Directory Layout

```
nexus_omega/
├── docker-compose.yml              # PostgreSQL + pgvector, Redis, and APEX-1 runtime
├── Dockerfile                      # Unified Python 3.11 runtime environment
├── deploy.sh                       # 1-Click zero-config autonomous bootloader
├── requirements.txt                # Python dependencies
├── master_build.py                 # Central cognitive orchestrator & 24/7 supervisor
├── cli.py                          # Headless terminal CLI & interactive shell
├── test_apex.py                    # Unit and integration test suite
├── init_db.sql                     # PostgreSQL schema with pgvector IVFFlat indexing
├── config/
│   ├── settings.py                 # Unified system configuration loader
│   ├── config.yaml                 # Provider models, timeouts, and baseline parameters
│   └── profiles.json               # Swarm worker personas and operational directives
├── core/
│   ├── router.py                   # Multi-LLM provider abstraction (OpenRouter/Gemini/Claude/Ollama)
│   ├── kanban.py                   # Asynchronous task graph and state transitions
│   ├── memory.py                   # PostgreSQL pgvector long-term persistence
│   └── scientific_learner.py       # Single-variable optimizer and reflection ledger
├── interfaces/
│   ├── web_server.py               # FastAPI backend & WebSocket event broadcaster
│   ├── telegram_bot.py             # Telegram bot command listener and push alerts
│   └── livekit_voice.py            # Multimodal WebRTC audio & vision bridge
├── tools/
│   ├── bash_sandbox.py             # Asynchronous shell execution sandbox
│   ├── duckduckgo_search.py        # Live unconstrained web intelligence extraction
│   └── messaging.py                # Telegram push notifications and dispatch
└── web/
    ├── index.html                  # Cybernetic glassmorphic Control Center UI
    ├── style.css                   # Obsidian dark mode stylesheet & responsive design
    └── app.js                      # Real-time WebSocket client, canvas visualizer, modals
```

---

## 4. Quick Start

### 4.1 Native Python

```powershell
cd nexus_omega
python master_build.py
```
* **Dashboard:** Open `http://localhost:8000` in your browser.
* **WebSocket Streams:** `ws://localhost:8000/ws/events` and `ws://localhost:8000/ws/logs`.

### 4.2 Headless CLI

```powershell
# Show system status & Kanban board
python cli.py status

# Submit a new directive
python cli.py goal "Conduct security audit of target infrastructure"

# View scientific optimizer ledger
python cli.py metrics

# Enter interactive shell
python cli.py
```

### 4.3 Docker Deployment

```bash
cd nexus_omega
bash deploy.sh
```

---

## 5. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the Kanban Web Control Center |
| `GET` | `/api/tasks` | Returns all tasks and status matrix counts |
| `POST` | `/api/tasks/action` | Performs task actions (`resume`, `block`) |
| `GET` | `/api/goals` | Returns registered goals |
| `POST` | `/api/goals` | Ingests and decomposes a new goal directive |
| `POST` | `/api/command` | Quick command dispatch to supervisor |
| `GET` | `/api/metrics` | System telemetry, uptime, and baseline stats |
| `GET` | `/api/optimizer/ledger` | Parameter learning ledger and active mutations |
| `WS` | `/ws/events` | Real-time Kanban state change broadcasting |
| `WS` | `/ws/logs` | Live streaming agent reasoning logs |

---

## 6. Testing

Run the full integration test suite:

```powershell
cd nexus_omega
python test_apex.py
```
Output:
```
Ran 5 tests in 0.219s
OK
```
