"""
Team Memory — Shared knowledge store so agents on the same team
share research findings and don't duplicate work.

Each team gets its own memory file. Agents append findings and
query past entries by keyword or topic.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path


class TeamMemory:
    """
    Append-only knowledge store with deduplication.
    Agents write discoveries; all agents on the same team can read them.
    """

    def __init__(self, team_id, memory_dir="./team_bus/memory"):
        self.TeamId = team_id
        self.MemoryDir = Path(memory_dir)
        self.MemoryDir.mkdir(parents=True, exist_ok=True)
        self.MemoryFile = self.MemoryDir / f"{team_id}.json"

        self.Entries = self.Load()

    def Load(self):
        if self.MemoryFile.exists():
            try:
                return json.loads(self.MemoryFile.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                pass
        return []

    def Save(self):
        self.MemoryFile.write_text(json.dumps(self.Entries, indent=2), encoding="utf-8")

    def Timestamp(self):
        return datetime.now(timezone.utc).isoformat()

    def Add(self, topic, content, source_agent, confidence="medium", tags=None):
        """
        Add a knowledge entry. Deduplicates by topic — if an entry
        with the same topic exists from the same agent, it's updated.
        """
        # Check for existing entry with same topic
        for entry in self.Entries:
            if entry["topic"].lower() == topic.lower():
                # Update existing with new info
                entry["content"] = content
                entry["updated_at"] = self.Timestamp()
                entry["updated_by"] = source_agent
                entry["confidence"] = confidence
                if tags:
                    existing_tags = set(entry.get("tags", []))
                    existing_tags.update(tags)
                    entry["tags"] = sorted(existing_tags)
                self.Save()
                return entry

        entry = {
            "topic": topic,
            "content": content,
            "source_agent": source_agent,
            "confidence": confidence,
            "tags": sorted(tags or []),
            "created_at": self.Timestamp(),
            "updated_at": self.Timestamp(),
            "updated_by": source_agent
        }

        self.Entries.append(entry)
        self.Save()
        return entry

    def Query(self, keyword=None, tag=None, source_agent=None, limit=20):
        """
        Search memory entries. Matches against topic, content, and tags.
        Returns most recent matches first.
        """
        results = []

        for entry in self.Entries:
            if keyword:
                kw = keyword.lower()
                if kw not in entry["topic"].lower() and kw not in entry["content"].lower():
                    continue
            if tag:
                if tag not in entry.get("tags", []):
                    continue
            if source_agent:
                if entry["source_agent"] != source_agent:
                    continue
            results.append(entry)

        results.sort(key=lambda e: e.get("updated_at", ""), reverse=True)
        return results[:limit]

    def GetAll(self):
        """Return all entries, most recent first."""
        return sorted(self.Entries, key=lambda e: e.get("updated_at", ""), reverse=True)

    def GetContextForAgent(self, max_entries=10):
        """
        Produce a condensed context string that can be injected
        into a task prompt so the agent knows what the team already knows.
        """
        recent = self.GetAll()[:max_entries]
        if not recent:
            return ""

        lines = ["TEAM KNOWLEDGE (what your team already knows):"]
        for e in recent:
            lines.append(f"- [{e['confidence']}] {e['topic']}: {e['content'][:200]}")
            lines.append(f"  (from {e['source_agent']}, {e['updated_at']})")

        return "\n".join(lines)

    def Clear(self):
        """Wipe all memory for this team."""
        self.Entries = []
        self.Save()
