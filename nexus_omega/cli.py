"""
NEXUS-OMEGA (APEX-1) - Headless Terminal CLI
Provides a command-line interface for autonomous swarm operations,
Kanban state inspection, goal dispatch, and live status monitoring.
"""

import argparse
import asyncio
import os
import sys
import json
import site

# Path setup
user_site = site.getusersitepackages()
if os.path.exists(user_site) and user_site not in sys.path:
    sys.path.insert(0, user_site)

project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import aiohttp  # type: ignore
from config.settings import config


BANNER = r"""
========================================================================
     _   _ _______  ___   _ ____        ___  __  __ _____ ____    _    
    | \ | | ____\ \/ / | | / ___|      / _ \|  \/  | ____/ ___|  / \   
    |  \| |  _|  \  /| | | \___ \ ____| | | | |\/| |  _|| |  _  / _ \  
    | |\  | |___ /  \| |_| |___) |_____| |_| | |  | | |__| |_| |/ ___ \ 
    |_| \_|_____/_/\_\\___/|____/       \___/|_|  |_|_____\____/_/   \_\\
                        APEX-1 :: HEADLESS CLI
========================================================================
"""

API_BASE = f"http://127.0.0.1:{config.WEB_PORT}"


async def check_daemon_online() -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE}/api/metrics", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                return resp.status == 200
    except Exception:
        return False


async def cmd_status():
    print(BANNER)
    online = await check_daemon_online()
    if not online:
        print("[!] APEX-1 Daemon is offline. Start it with: python master_build.py\n")
        return

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/api/tasks") as resp:
            data = await resp.json()
            tasks = data.get("tasks", [])
            summary = data.get("summary", {})

        async with session.get(f"{API_BASE}/api/metrics") as resp:
            metrics = await resp.json()

    print("[+] SYSTEM STATUS: ACTIVE 24/7")
    print(f"[+] MODEL ROUTE:   {metrics.get('model', 'Unknown')}")
    print(f"[+] UPTIME SINCE:  {metrics.get('uptime_since', 'N/A')}\n")

    print("-" * 72)
    print(" KANBAN STATE MATRIX")
    print("-" * 72)
    cols = ["TODO", "READY", "IN_PROGRESS", "BLOCKED", "DONE"]
    header = " | ".join(f"{c}: {summary.get(c, 0):2d}" for c in cols)
    print(f" {header}")
    print("-" * 72)

    if tasks:
        print("\n ACTIVE TASKS:")
        for t in tasks[-8:]:
            status_tag = f"[{t.get('status', 'N/A'):11s}]"
            agent_tag = f"<{t.get('assigned_agent') or 'Supervisor'}>"
            print(f"  {status_tag} {agent_tag:22s} #{t.get('id', ''):14s} {t.get('title', '')}")
    else:
        print("\n No tasks currently in queue.")
    print()


async def cmd_goal(goal_text: str):
    online = await check_daemon_online()
    if not online:
        print("[!] APEX-1 Daemon is offline. Booting in standalone one-shot mode...")
        from master_build import ApexSupervisor
        supervisor = ApexSupervisor()
        print(f"[*] Ingesting directive: {goal_text}")
        await supervisor.ingest_high_level_goal(goal_text)
        print("[*] Running autonomous worker swarm pipeline...")
        ready = supervisor.kanban.get_ready_tasks()
        for task in ready:
            agent = supervisor._select_agent_for_task(task.title, task.instruction)
            print(f"[*] Dispatching to [{agent['name']}]: {task.title}")
            await supervisor._execute_task_pipeline(task, agent)
        print("[✓] Execution complete.")
        return

    async with aiohttp.ClientSession() as session:
        payload = {"title": goal_text[:80], "description": goal_text}
        async with session.post(f"{API_BASE}/api/goals", json=payload) as resp:
            if resp.status == 200:
                print(f"[✓] Goal dispatched to supervisor: {goal_text}")
            else:
                print(f"[!] Failed to submit goal: {await resp.text()}")


async def cmd_resume(task_id: str):
    async with aiohttp.ClientSession() as session:
        payload = {"task_id": task_id, "action": "resume"}
        async with session.post(f"{API_BASE}/api/tasks/action", json=payload) as resp:
            if resp.status == 200:
                print(f"[✓] Task #{task_id} resumed.")
            else:
                print(f"[!] Failed to resume task: {await resp.text()}")


async def cmd_metrics():
    online = await check_daemon_online()
    if not online:
        print("[!] APEX-1 Daemon is offline.")
        return

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/api/optimizer/ledger") as resp:
            data = await resp.json()
            print("\n" + "=" * 60)
            print(" SCIENTIFIC OPTIMIZER & BASELINE PARAMETER LEDGER")
            print("=" * 60)
            print(f" Total Experiments:   {data.get('total_experiments', 0)}")
            print(f" Adopted Mutations:   {data.get('adoptions', 0)}")
            print(f" Rejection Rate:      {data.get('rejection_rate', 0.0) * 100:.1f}%")
            print(f" Current Baseline:    {data.get('current_baseline_score', 0.75):.4f}")
            print("\n Active Parameters:")
            for k, v in data.get("active_parameters", {}).items():
                print(f"   • {k:18s}: {v}")
            print("=" * 60 + "\n")


async def interactive_shell():
    print(BANNER)
    print("Type 'help' for command list or 'exit' to quit.\n")
    while True:
        try:
            line = input("APEX-1> ").strip()
            if not line:
                continue
            if line.lower() in ("exit", "quit"):
                break
            elif line.lower() == "help":
                print("Commands:")
                print("  status            - Show Kanban state and metrics")
                print("  goal <text>       - Dispatch an autonomous directive")
                print("  resume <task_id>  - Resume a BLOCKED task")
                print("  metrics           - Show scientific optimizer ledger")
                print("  exit              - Exit CLI")
            elif line.lower() == "status":
                await cmd_status()
            elif line.lower() == "metrics":
                await cmd_metrics()
            elif line.lower().startswith("goal "):
                await cmd_goal(line[5:].strip())
            elif line.lower().startswith("resume "):
                await cmd_resume(line[7:].strip())
            else:
                # Treat as raw directive
                await cmd_goal(line)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break


def main():
    parser = argparse.ArgumentParser(description="NEXUS-OMEGA (APEX-1) Headless CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show Kanban board status")
    subparsers.add_parser("metrics", help="Show scientific learning ledger")

    goal_parser = subparsers.add_parser("goal", help="Submit a new autonomous goal")
    goal_parser.add_argument("text", nargs="+", help="Goal text directive")

    resume_parser = subparsers.add_parser("resume", help="Resume a blocked task")
    resume_parser.add_argument("task_id", help="ID of task to resume")

    args = parser.parse_args()

    if args.command == "status":
        asyncio.run(cmd_status())
    elif args.command == "metrics":
        asyncio.run(cmd_metrics())
    elif args.command == "goal":
        asyncio.run(cmd_goal(" ".join(args.text)))
    elif args.command == "resume":
        asyncio.run(cmd_resume(args.task_id))
    else:
        asyncio.run(interactive_shell())


if __name__ == "__main__":
    main()
