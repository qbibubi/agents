"""
Budget Tracker — Enforces spending limits across all agents and teams.
Reads budget.yaml for caps, tracks cumulative spend in a JSON file,
and blocks API calls when caps are exceeded.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class BudgetTracker:
    """
    Tracks spend per agent, per team, and globally.
    Persists to disk so spending survives agent restarts.
    """

    def __init__(self, budget_config, tracker_file="./team_bus/budget_tracker.json"):
        self.Config = budget_config
        self.TrackerFile = Path(tracker_file)
        self.TrackerFile.parent.mkdir(parents=True, exist_ok=True)

        self.State = self.LoadState()
        self.ResetIfNeeded()

    def LoadState(self):
        if self.TrackerFile.exists():
            try:
                return json.loads(self.TrackerFile.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                pass

        return {
            "global": {"daily": 0.0, "monthly": 0.0},
            "teams": {},
            "agents": {},
            "daily_reset_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "monthly_reset_at": datetime.now(timezone.utc).strftime("%Y-%m")
        }

    def SaveState(self):
        self.TrackerFile.write_text(json.dumps(self.State, indent=2), encoding="utf-8")

    def ResetIfNeeded(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        month = datetime.now(timezone.utc).strftime("%Y-%m")

        changed = False

        if self.State.get("daily_reset_at") != today:
            self.State["global"]["daily"] = 0.0
            for team in self.State["teams"].values():
                team["daily"] = 0.0
            for agent in self.State["agents"].values():
                agent["daily"] = 0.0
            self.State["daily_reset_at"] = today
            changed = True

        if self.State.get("monthly_reset_at") != month:
            self.State["global"]["monthly"] = 0.0
            for team in self.State["teams"].values():
                team["monthly"] = 0.0
            for agent in self.State["agents"].values():
                agent["monthly"] = 0.0
            self.State["monthly_reset_at"] = month
            changed = True

        if changed:
            self.SaveState()

    def GetAgentCap(self, agent_id):
        caps = self.Config.get("budget", {}).get("agent_caps", {})
        overrides = caps.get("overrides", {})
        if agent_id in overrides:
            return overrides[agent_id]
        return caps.get("default", {"daily": 1.0, "monthly": 10.0})

    def GetTeamCap(self, team_id):
        caps = self.Config.get("budget", {}).get("team_caps", {})
        return caps.get(team_id, {"daily": 0.0, "monthly": 0.0})

    def GetGlobalCap(self, period):
        caps = self.Config.get("budget", {})
        return caps.get(f"global_{period}_cap", 0.0)

    def GetOveragePolicy(self):
        return self.Config.get("budget", {}).get("overage_policy", "block")

    def GetFallback(self):
        cfg = self.Config.get("budget", {})
        return cfg.get("fallback_provider", "local"), cfg.get("fallback_model", "llama3-8b")

    def GetWarnPercent(self):
        return self.Config.get("budget", {}).get("warn_at_percent", 80)

    def CheckBudget(self, agent_id, team_id=None):
        """
        Check if the agent is allowed to make an API call.
        Returns: (allowed: bool, reason: str, fallback_provider: str, fallback_model: str)
        """
        self.ResetIfNeeded()

        agent_cap = self.GetAgentCap(agent_id)
        agent_spend = self.State["agents"].get(agent_id, {"daily": 0.0, "monthly": 0.0})

        # Check agent daily cap
        if agent_cap.get("daily", 0) > 0:
            if agent_spend.get("daily", 0.0) >= agent_cap["daily"]:
                policy = self.GetOveragePolicy()
                if policy == "block":
                    return False, f"Agent {agent_id} daily cap reached (${agent_cap['daily']:.2f})", None, None
                elif policy == "local":
                    fb_prov, fb_model = self.GetFallback()
                    return True, f"Agent {agent_id} over cap, switching to local", fb_prov, fb_model
                # "warn" falls through

        # Check agent monthly cap
        if agent_cap.get("monthly", 0) > 0:
            if agent_spend.get("monthly", 0.0) >= agent_cap["monthly"]:
                policy = self.GetOveragePolicy()
                if policy == "block":
                    return False, f"Agent {agent_id} monthly cap reached (${agent_cap['monthly']:.2f})", None, None
                elif policy == "local":
                    fb_prov, fb_model = self.GetFallback()
                    return True, f"Agent {agent_id} over cap, switching to local", fb_prov, fb_model

        # Check team caps
        if team_id:
            team_cap = self.GetTeamCap(team_id)
            team_spend = self.State["teams"].get(team_id, {"daily": 0.0, "monthly": 0.0})

            if team_cap.get("daily", 0) > 0:
                if team_spend.get("daily", 0.0) >= team_cap["daily"]:
                    policy = self.GetOveragePolicy()
                    if policy == "block":
                        return False, f"Team {team_id} daily cap reached (${team_cap['daily']:.2f})", None, None
                    elif policy == "local":
                        fb_prov, fb_model = self.GetFallback()
                        return True, f"Team {team_id} over cap, switching to local", fb_prov, fb_model

            if team_cap.get("monthly", 0) > 0:
                if team_spend.get("monthly", 0.0) >= team_cap["monthly"]:
                    policy = self.GetOveragePolicy()
                    if policy == "block":
                        return False, f"Team {team_id} monthly cap reached (${team_cap['monthly']:.2f})", None, None
                    elif policy == "local":
                        fb_prov, fb_model = self.GetFallback()
                        return True, f"Team {team_id} over cap, switching to local", fb_prov, fb_model

        # Check global caps
        global_spend = self.State["global"]

        global_daily = self.GetGlobalCap("daily")
        if global_daily > 0 and global_spend.get("daily", 0.0) >= global_daily:
            policy = self.GetOveragePolicy()
            if policy == "block":
                return False, f"Global daily cap reached (${global_daily:.2f})", None, None
            elif policy == "local":
                fb_prov, fb_model = self.GetFallback()
                return True, f"Global over cap, switching to local", fb_prov, fb_model

        global_monthly = self.GetGlobalCap("monthly")
        if global_monthly > 0 and global_spend.get("monthly", 0.0) >= global_monthly:
            policy = self.GetOveragePolicy()
            if policy == "block":
                return False, f"Global monthly cap reached (${global_monthly:.2f})", None, None
            elif policy == "local":
                fb_prov, fb_model = self.GetFallback()
                return True, f"Global over cap, switching to local", fb_prov, fb_model

        # Check warn thresholds
        warn_pct = self.GetWarnPercent()
        warnings = []

        if agent_cap.get("daily", 0) > 0:
            pct = (agent_spend.get("daily", 0.0) / agent_cap["daily"]) * 100
            if pct >= warn_pct:
                warnings.append(f"Agent {agent_id} daily at {pct:.0f}%")

        if team_id:
            team_cap = self.GetTeamCap(team_id)
            if team_cap.get("daily", 0) > 0:
                team_spend = self.State["teams"].get(team_id, {"daily": 0.0, "monthly": 0.0})
                pct = (team_spend.get("daily", 0.0) / team_cap["daily"]) * 100
                if pct >= warn_pct:
                    warnings.append(f"Team {team_id} daily at {pct:.0f}%")

        if global_daily > 0:
            pct = (global_spend.get("daily", 0.0) / global_daily) * 100
            if pct >= warn_pct:
                warnings.append(f"Global daily at {pct:.0f}%")

        return True, "; ".join(warnings) if warnings else "OK", None, None

    def RecordSpend(self, agent_id, cost_usd, team_id=None):
        """
        Record a spend event after an API call completes.
        Updates agent, team, and global tallies.
        """
        self.ResetIfNeeded()

        # Agent
        if agent_id not in self.State["agents"]:
            self.State["agents"][agent_id] = {"daily": 0.0, "monthly": 0.0}
        self.State["agents"][agent_id]["daily"] += cost_usd
        self.State["agents"][agent_id]["monthly"] += cost_usd

        # Team
        if team_id:
            if team_id not in self.State["teams"]:
                self.State["teams"][team_id] = {"daily": 0.0, "monthly": 0.0}
            self.State["teams"][team_id]["daily"] += cost_usd
            self.State["teams"][team_id]["monthly"] += cost_usd

        # Global
        self.State["global"]["daily"] += cost_usd
        self.State["global"]["monthly"] += cost_usd

        self.SaveState()

    def GetStatus(self):
        """Return a human-readable budget status summary."""
        self.ResetIfNeeded()

        global_daily = self.GetGlobalCap("daily")
        global_monthly = self.GetGlobalCap("monthly")

        lines = []
        lines.append(f"Global: ${self.State['global']['daily']:.4f} / ${global_daily:.2f} daily, "
                      f"${self.State['global']['monthly']:.4f} / ${global_monthly:.2f} monthly")

        for agent_id, spend in self.State.get("agents", {}).items():
            cap = self.GetAgentCap(agent_id)
            lines.append(f"  {agent_id}: ${spend['daily']:.4f} / ${cap.get('daily', 0):.2f} daily")

        for team_id, spend in self.State.get("teams", {}).items():
            cap = self.GetTeamCap(team_id)
            lines.append(f"  Team {team_id}: ${spend['daily']:.4f} / ${cap.get('daily', 0):.2f} daily")

        return "\n".join(lines)
