"""
JARVIS Trainer
==============
Manages locally-trained custom command → response pairs stored in Supabase.

The router checks trained commands FIRST before calling the AI model,
giving you deterministic overrides for specific phrases.

Supabase table (run once in Supabase SQL Editor):
--------------------------------------------------
CREATE TABLE IF NOT EXISTS jarvis_training (
    id          BIGSERIAL PRIMARY KEY,
    trigger     TEXT NOT NULL,
    response    TEXT NOT NULL,
    category    TEXT DEFAULT 'general',
    enabled     BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Full-text search index for fast matching
CREATE INDEX IF NOT EXISTS idx_training_trigger ON jarvis_training (lower(trigger));
"""

from __future__ import annotations

import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SUPABASE_URL      = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

TABLE = "jarvis_training"


class JarvisTrainer:
    """
    Stores and retrieves trained command→response pairs from Supabase.
    Falls back gracefully when Supabase is not configured.
    """

    def __init__(self):
        self.available = bool(SUPABASE_URL and SUPABASE_ANON_KEY)
        self._client   = None
        self._cache    = []     # local cache: list of {id, trigger, response, ...}
        self._cache_ok = False

        if self.available:
            try:
                from supabase import create_client
                self._client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
                self._ensure_table()
                self._refresh_cache()
            except Exception as exc:
                logger.warning("Trainer init: %s", exc)
                self.available = False

    # ── table bootstrap ───────────────────────────────────────────────────────

    def _ensure_table(self):
        """Silently verify table exists (cannot create via anon key — user must do it)."""
        try:
            self._client.table(TABLE).select("id").limit(1).execute()
        except Exception as exc:
            logger.warning(
                "jarvis_training table may not exist. "
                "Run the CREATE TABLE SQL in your Supabase dashboard. "
                "Error: %s", exc
            )

    # ── cache ─────────────────────────────────────────────────────────────────

    def _refresh_cache(self):
        """Load all enabled commands into local cache for fast matching."""
        try:
            res = (
                self._client.table(TABLE)
                .select("id,trigger,response,category,enabled")
                .eq("enabled", True)
                .order("created_at", desc=False)
                .execute()
            )
            self._cache    = res.data or []
            self._cache_ok = True
        except Exception as exc:
            logger.warning("Trainer cache refresh: %s", exc)

    # ── matching ──────────────────────────────────────────────────────────────

    def find_match(self, text: str) -> Optional[str]:
        """
        Check if `text` matches any trained command trigger.
        Matching rules (in order):
          1. Exact match (case-insensitive)
          2. Trigger is a substring of text
          3. Text contains all words of the trigger
        Returns the response string, or None if no match.
        """
        if not self._cache:
            return None

        normalized = text.lower().strip().rstrip(".?!")

        for cmd in self._cache:
            trigger = cmd.get("trigger", "").lower().strip()
            if not trigger:
                continue

            # 1. Exact match
            if normalized == trigger:
                return cmd["response"]

            # 2. Trigger is substring
            if trigger in normalized:
                return cmd["response"]

            # 3. All significant words of trigger appear in text
            words = [w for w in trigger.split() if len(w) > 2]
            if words and all(w in normalized for w in words):
                return cmd["response"]

        return None

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_command(
        self,
        trigger: str,
        response: str,
        category: str = "general",
    ) -> dict:
        """
        Store a trained command in Supabase.
        Returns {"success": True, "id": ...} or {"success": False, "error": ...}
        """
        if not self.available:
            return {"success": False, "error": "Supabase not configured."}

        trigger  = trigger.strip().lower()
        response = response.strip()

        if not trigger or not response:
            return {"success": False, "error": "Trigger and response cannot be empty."}

        try:
            res = (
                self._client.table(TABLE)
                .insert({
                    "trigger":  trigger,
                    "response": response,
                    "category": category,
                    "enabled":  True,
                })
                .execute()
            )
            row = res.data[0] if res.data else {}
            self._cache.append(row)
            return {"success": True, "id": row.get("id"), "data": row}
        except Exception as exc:
            logger.warning("Trainer add: %s", exc)
            return {"success": False, "error": str(exc)}

    def get_commands(self, category: str = None) -> list[dict]:
        """Fetch all trained commands (all enabled + disabled for editing UI)."""
        if not self.available:
            return []
        try:
            q = self._client.table(TABLE).select("*").order("created_at", desc=True)
            if category:
                q = q.eq("category", category)
            res = q.execute()
            return res.data or []
        except Exception as exc:
            logger.warning("Trainer get: %s", exc)
            return []

    def delete_command(self, command_id: int) -> bool:
        """Delete a trained command by ID."""
        if not self.available:
            return False
        try:
            self._client.table(TABLE).delete().eq("id", command_id).execute()
            self._cache = [c for c in self._cache if c.get("id") != command_id]
            return True
        except Exception as exc:
            logger.warning("Trainer delete: %s", exc)
            return False

    def toggle_command(self, command_id: int, enabled: bool) -> bool:
        """Enable or disable a trained command."""
        if not self.available:
            return False
        try:
            self._client.table(TABLE).update({"enabled": enabled}).eq("id", command_id).execute()
            for c in self._cache:
                if c.get("id") == command_id:
                    c["enabled"] = enabled
            if not enabled:
                self._cache = [c for c in self._cache if c.get("id") != command_id]
            else:
                self._refresh_cache()
            return True
        except Exception as exc:
            logger.warning("Trainer toggle: %s", exc)
            return False

    def update_command(
        self,
        command_id: int,
        trigger: str = None,
        response: str = None,
        category: str = None,
    ) -> bool:
        """Update fields of a trained command."""
        if not self.available:
            return False
        updates = {}
        if trigger  is not None: updates["trigger"]  = trigger.strip().lower()
        if response is not None: updates["response"] = response.strip()
        if category is not None: updates["category"] = category
        if not updates:
            return True
        try:
            self._client.table(TABLE).update(updates).eq("id", command_id).execute()
            self._refresh_cache()
            return True
        except Exception as exc:
            logger.warning("Trainer update: %s", exc)
            return False

    def get_categories(self) -> list[str]:
        """Get distinct categories."""
        cmds = self.get_commands()
        seen = set()
        cats = []
        for c in cmds:
            cat = c.get("category", "general")
            if cat not in seen:
                seen.add(cat)
                cats.append(cat)
        return cats or ["general"]
