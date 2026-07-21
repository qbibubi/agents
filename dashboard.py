"""
Team Dashboard — Real-time view of all agents, tasks, and results.
Run this in a separate terminal to monitor the team.
"""

import os
import sys
import time
from pathlib import Path
from message_bus import MessageBus


def ClearScreen():
    os.system("cls" if os.name == "nt" else "clear")


def PrintDashboard(bus):
    ClearScreen()

    print("=" * 65)
    print("  AI DEV TEAM — DASHBOARD")
    print("=" * 65)

    status = bus.GetTeamStatus()

    print(f"\n  Tasks: {status['total']} total | "
          f"{status['pending']} pending | "
          f"{status['in_progress']} in progress | "
          f"{status['completed']} completed")

    print("\n  --- BY AGENT ---")
    for agent_id, counts in status.get("by_agent", {}).items():
        bar = ""
        if counts.get("in_progress"):
            bar += f"[WORKING: {counts['in_progress']}] "
        if counts.get("pending"):
            bar += f"[QUEUED: {counts['pending']}] "
        if counts.get("completed"):
            bar += f"[DONE: {counts['completed']}]"
        print(f"    {agent_id:20s} {bar}")

    print("\n  --- RECENT ACTIVITY ---")
    for agent_id in ["orchestrator", "researcher", "coder", "reviewer", "bus"]:
        log = bus.GetLog(agent_id, tail=3)
        if log:
            for line in log.split("\n")[-3:]:
                if line.strip():
                    print(f"    [{agent_id}] {line.split('] ', 1)[-1] if '] ' in line else line}")

    print("\n  --- RECENT RESULTS ---")
    results = bus.ListResults()
    for r in results[-5:]:
        print(f"    [{r['agent_id']}] {r.get('summary', r['task_id'])} — {r['status']}")

    print("\n" + "=" * 65)
    print("  Refreshing every 5s | Ctrl+C to exit")


if __name__ == "__main__":
    ScriptDir = Path(__file__).resolve().parent
    bus = MessageBus(str(ScriptDir / "team_bus"))

    try:
        while True:
            PrintDashboard(bus)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nDashboard closed.")
