"""
JARVIS Memory — Supabase-backed persistent memory.

Stores user-defined facts and conversation logs so JARVIS can
recall them across sessions.

Requires in .env (project root):
    SUPABASE_URL=https://xxxx.supabase.co
    SUPABASE_ANON_KEY=your-anon-key

If env vars are missing, every method is a no-op and returns None.

Supabase tables required (SQL to run in Supabase SQL editor):

    CREATE TABLE jarvis_memory (
        id          BIGSERIAL PRIMARY KEY,
        key         TEXT NOT NULL,
        value       TEXT NOT NULL,
        created_at  TIMESTAMPTZ DEFAULT now()
    );

    CREATE TABLE jarvis_log (
        id          BIGSERIAL PRIMARY KEY,
        session_id  TEXT NOT NULL DEFAULT 'default',
        role        TEXT NOT NULL,
        content     TEXT NOT NULL,
        created_at  TIMESTAMPTZ DEFAULT now()
    );
"""

import os


def _get_client():
    """Return a Supabase client, or None if credentials are missing."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_ANON_KEY", "").strip()

    if not url or not key:
        return None

    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        print(f"[Memory] Supabase init failed: {exc}")
        return None


class JarvisMemory:
    def __init__(self):
        self._client = _get_client()
        self._session = os.getenv("JARVIS_SESSION_ID", "default")

        if self._client:
            print("[Memory] Supabase memory connected.")
        else:
            print(
                "[Memory] Supabase not configured — "
                "memory features disabled."
            )

    @property
    def available(self):
        return self._client is not None

    # ------------------------------------------------------------------
    # STORE A FACT
    # ------------------------------------------------------------------

    def store(self, key: str, value: str) -> bool:
        """
        Save or update a key→value fact.
        Returns True on success.
        """
        if not self._client:
            return False

        key = key.lower().strip()
        value = value.strip()

        try:
            # Upsert: update if key exists, insert if not.
            # Supabase doesn't support upsert on non-pk easily,
            # so delete-then-insert.
            self._client.table("jarvis_memory").delete().eq(
                "key", key
            ).execute()

            self._client.table("jarvis_memory").insert(
                {"key": key, "value": value}
            ).execute()

            print(f"[Memory] Stored: {key!r} = {value!r}")
            return True

        except Exception as exc:
            print(f"[Memory] Store error: {exc}")
            return False

    # ------------------------------------------------------------------
    # RECALL A FACT
    # ------------------------------------------------------------------

    def recall(self, key: str) -> str | None:
        """Return the value for a key, or None if not found."""
        if not self._client:
            return None

        key = key.lower().strip()

        try:
            result = (
                self._client.table("jarvis_memory")
                .select("value")
                .eq("key", key)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0]["value"]

            return None

        except Exception as exc:
            print(f"[Memory] Recall error: {exc}")
            return None

    # ------------------------------------------------------------------
    # SEARCH FACTS (fuzzy keyword match)
    # ------------------------------------------------------------------

    def search(self, query: str) -> list[dict]:
        """
        Return up to 5 memory entries whose key or value contains
        the query string.
        """
        if not self._client:
            return []

        query = query.lower().strip()

        try:
            result = (
                self._client.table("jarvis_memory")
                .select("key, value")
                .ilike("key", f"%{query}%")
                .limit(5)
                .execute()
            )

            rows = result.data or []

            if not rows:
                result2 = (
                    self._client.table("jarvis_memory")
                    .select("key, value")
                    .ilike("value", f"%{query}%")
                    .limit(5)
                    .execute()
                )
                rows = result2.data or []

            return rows

        except Exception as exc:
            print(f"[Memory] Search error: {exc}")
            return []

    # ------------------------------------------------------------------
    # LIST ALL FACTS
    # ------------------------------------------------------------------

    def list_all(self) -> list[dict]:
        """Return all stored memory entries."""
        if not self._client:
            return []

        try:
            result = (
                self._client.table("jarvis_memory")
                .select("key, value, created_at")
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            )
            return result.data or []

        except Exception as exc:
            print(f"[Memory] List error: {exc}")
            return []

    # ------------------------------------------------------------------
    # LOG CONVERSATION TURN
    # ------------------------------------------------------------------

    def log(self, role: str, content: str) -> None:
        """
        Append a conversation turn to jarvis_log.
        role: 'user' or 'assistant'
        """
        if not self._client:
            return

        try:
            self._client.table("jarvis_log").insert(
                {
                    "session_id": self._session,
                    "role": role,
                    "content": content,
                }
            ).execute()

        except Exception as exc:
            print(f"[Memory] Log error: {exc}")
