"""
Message Bus Protocol — File-based communication layer for the AI agent team.

Agents read tasks from team_bus/tasks/, write results to team_bus/results/,
and log activity to team_bus/logs/. This is the ONLY way agents communicate.

All writes use write-temp-then-rename (atomic on Windows and POSIX) to
prevent readers from seeing partial files. All reads use a short retry
backoff to handle the narrow window where a rename isn't yet visible.
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# ATOMIC I/O PRIMITIVES
# ---------------------------------------------------------------------------

def AtomicWriteJson(filepath, data):
    """
    Write JSON atomically: write to temp file in same directory, fsync,
    then os.replace (atomic on Windows ReplaceFile and POSIX rename).
    A concurrent reader sees either the old complete file or the new
    complete file — never a truncated or half-written one.
    """
    directory = filepath.parent
    tmp_path = directory / f".tmp_{uuid.uuid4().hex}_{filepath.name}"

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, filepath)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def ReadJsonRetry(filepath, retries=3, delay=0.05):
    """
    Read JSON with retry backoff. Guards against the rare window on some
    filesystems where a concurrent rename isn't immediately visible.
    """
    last_err = None
    for attempt in range(retries):
        try:
            return json.loads(filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError) as e:
            last_err = e
            time.sleep(delay * (attempt + 1))
    raise last_err


# ---------------------------------------------------------------------------
# MESSAGE BUS
# ---------------------------------------------------------------------------

class MessageBus:
    """
    Shared communication bus for all agents on the team.
    Each agent gets its own MessageBus instance pointed at the shared directories.
    """

    def __init__(self, bus_dir="./team_bus"):
        self.BusDir = Path(bus_dir)
        self.TaskDir = self.BusDir / "tasks"
        self.ResultDir = self.BusDir / "results"
        self.LogDir = self.BusDir / "logs"

        for d in [self.TaskDir, self.ResultDir, self.LogDir]:
            d.mkdir(parents=True, exist_ok=True)

    def Timestamp(self):
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # TASK OPERATIONS
    # ------------------------------------------------------------------

    def CreateTask(self, assigned_to, title, description, context=None,
                   priority=3, output_format="json", parent_task_id=None):
        """Create a new task file and assign it to an agent."""
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        task = {
            "task_id": task_id,
            "assigned_to": assigned_to,
            "priority": priority,
            "status": "pending",
            "title": title,
            "description": description,
            "context": context or {},
            "output_format": output_format,
            "parent_task_id": parent_task_id,
            "created_at": self.Timestamp(),
            "claimed_at": None,
            "completed_at": None
        }

        filepath = self.TaskDir / f"{task_id}.json"
        AtomicWriteJson(filepath, task)

        self.Log("bus", f"Created task {task_id} -> {assigned_to}: {title}")
        return task_id

    def ClaimTask(self, agent_id):
        """
        Claim the highest-priority pending task assigned to this agent.
        Uses a lockfile (O_CREAT | O_EXCL) to prevent two workers from
        claiming the same task concurrently.
        Returns the task dict, or None if no tasks are available.
        """
        tasks = self.ListPendingTasks(agent_id)
        if not tasks:
            return None

        # Sort by priority (1=highest) then by creation time
        tasks.sort(key=lambda t: (t.get("priority", 3), t.get("created_at", "")))

        task = tasks[0]
        # Use the actual file path from ListPendingTasks, not task_id reconstruction
        # This ensures filename and task_id mismatch doesn't cause a crash
        task_path = self.TaskDir / f"{task['task_id']}.json"
        if not task_path.exists():
            return None

        # Lockfile to close the claim TOCTOU race
        lock_path = self.TaskDir / f"{task['task_id']}.lock"

        # Check for stale lock (default: 300 seconds)
        if lock_path.exists():
            try:
                lock_age = time.time() - lock_path.stat().st_mtime
                if lock_age > 300:
                    lock_path.unlink()
                    self.Log("bus", f"Cleaned stale lock for {task['task_id']}")
            except OSError:
                pass

        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            return None

        try:
            # Re-read under lock to confirm it's still pending
            try:
                current = ReadJsonRetry(task_path)
            except (FileNotFoundError, json.JSONDecodeError):
                return None

            if current.get("status") != "pending":
                return None

            current["status"] = "in_progress"
            current["claimed_at"] = self.Timestamp()
            current["claimed_by"] = agent_id

            AtomicWriteJson(task_path, current)
            self.Log(agent_id, f"Claimed {task['task_id']}: {task['title']}")
            return current
        finally:
            try:
                lock_path.unlink()
            except OSError:
                pass

    def ListPendingTasks(self, agent_id=None):
        """List all pending tasks, optionally filtered by assigned agent."""
        tasks = []
        if not self.TaskDir.exists():
            return tasks

        for f in self.TaskDir.glob("*.json"):
            try:
                task = ReadJsonRetry(f)
                if task.get("status") != "pending":
                    continue
                if agent_id and task.get("assigned_to") != agent_id:
                    continue
                tasks.append(task)
            except (json.JSONDecodeError, KeyError, FileNotFoundError):
                continue

        return tasks

    def ListMyTasks(self, agent_id):
        """List all tasks (any status) assigned to this agent."""
        tasks = []
        if not self.TaskDir.exists():
            return tasks

        for f in self.TaskDir.glob("*.json"):
            try:
                task = ReadJsonRetry(f)
                if task.get("assigned_to") == agent_id:
                    tasks.append(task)
            except (json.JSONDecodeError, KeyError, FileNotFoundError):
                continue

        return tasks

    def GetTask(self, task_id):
        """Read a specific task by ID."""
        filepath = self.TaskDir / f"{task_id}.json"
        if not filepath.exists():
            return None
        try:
            return ReadJsonRetry(filepath)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    # ------------------------------------------------------------------
    # RESULT OPERATIONS
    # ------------------------------------------------------------------

    def PostResult(self, task_id, agent_id, status, data, summary=""):
        """Post a result for a completed task."""
        result_id = f"result_{task_id}"

        result = {
            "result_id": result_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "status": status,
            "summary": summary,
            "data": data,
            "posted_at": self.Timestamp()
        }

        filepath = self.ResultDir / f"{result_id}.json"
        AtomicWriteJson(filepath, result)

        # Mark task as completed
        task = self.GetTask(task_id)
        if task:
            task["status"] = "completed"
            task["completed_at"] = self.Timestamp()
            task_file = self.TaskDir / f"{task_id}.json"
            AtomicWriteJson(task_file, task)

        self.Log(agent_id, f"Posted result for {task_id}: {status}")
        return result_id

    def GetResult(self, task_id):
        """Get the result for a specific task."""
        filepath = self.ResultDir / f"result_{task_id}.json"
        if not filepath.exists():
            return None
        try:
            return ReadJsonRetry(filepath)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def ListResults(self, agent_id=None):
        """List all results, optionally filtered by agent."""
        results = []
        if not self.ResultDir.exists():
            return results

        for f in self.ResultDir.glob("*.json"):
            try:
                result = ReadJsonRetry(f)
                if agent_id and result.get("agent_id") != agent_id:
                    continue
                results.append(result)
            except (json.JSONDecodeError, KeyError, FileNotFoundError):
                continue

        return results

    def SendFeedback(self, task_id, feedback):
        """
        Send feedback on a result, re-opening the task for revision.
        Creates a new task with the feedback as context.
        """
        task = self.GetTask(task_id)
        if not task:
            return None

        result = self.GetResult(task_id)

        # Truncate prior context to avoid bloat on revision cycles.
        # Keep the original task description and a summary of the prior
        # result, but drop the full raw data to avoid 3x growth per revision.
        prior_summary = ""
        if result and result.get("data", {}).get("output"):
            raw = result["data"]["output"]
            if isinstance(raw, str):
                prior_summary = raw[:2000]
            else:
                prior_summary = json.dumps(raw)[:2000]

        new_context = {
            "original_task_description": task.get("description", "")[:2000],
            "previous_result_summary": prior_summary,
            "feedback": feedback
        }

        new_task_id = self.CreateTask(
            assigned_to=task["assigned_to"],
            title=f"REVISION: {task['title']}",
            description=f"Revise your previous work based on feedback.\n\nFEEDBACK:\n{feedback}",
            context=new_context,
            priority=1,
            parent_task_id=task_id
        )

        self.Log("bus", f"Feedback loop: {task_id} -> {new_task_id}")
        return new_task_id

    # ------------------------------------------------------------------
    # LOGGING
    # ------------------------------------------------------------------

    def Log(self, agent_id, message):
        """Append a log entry for the agent. Logs are append-only, no atomic rename needed."""
        log_file = self.LogDir / f"{agent_id}.log"
        entry = f"[{self.Timestamp()}] {message}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def GetLog(self, agent_id, tail=50):
        """Read the last N lines of an agent's log."""
        log_file = self.LogDir / f"{agent_id}.log"
        if not log_file.exists():
            return ""
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        return "\n".join(lines[-tail:])

    # ------------------------------------------------------------------
    # STATUS / DASHBOARD
    # ------------------------------------------------------------------

    def GetTeamStatus(self):
        """Return a summary of all tasks and their statuses."""
        tasks = []
        if self.TaskDir.exists():
            for f in self.TaskDir.glob("*.json"):
                try:
                    tasks.append(ReadJsonRetry(f))
                except (json.JSONDecodeError, KeyError, FileNotFoundError):
                    continue

        status = {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t.get("status") == "pending"),
            "in_progress": sum(1 for t in tasks if t.get("status") == "in_progress"),
            "completed": sum(1 for t in tasks if t.get("status") == "completed"),
            "by_agent": {}
        }

        for t in tasks:
            agent = t.get("assigned_to", "unassigned")
            if agent not in status["by_agent"]:
                status["by_agent"][agent] = {"pending": 0, "in_progress": 0, "completed": 0}
            st = t.get("status", "pending")
            status["by_agent"][agent][st] = status["by_agent"][agent].get(st, 0) + 1

        return status
