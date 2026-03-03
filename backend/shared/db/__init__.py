"""Shared database layer — Supabase client wrapper + connection pool.

URI: softwareos-base://backend/shared/db
"""

from .client import SupabaseClient, get_client

__all__ = ["SupabaseClient", "get_client"]
