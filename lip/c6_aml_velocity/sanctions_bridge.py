"""
sanctions_bridge.py — Python bridge to the Rust-backed C6 sanctions screener.

Architecture:
  1. Primary path: Import the PyO3 ``lip_c6_rust_velocity`` module compiled from
     ``lip/c6_aml_velocity/rust_velocity/``.  All screening operations delegate
     to the Rust ``PySanctionsScreener``: Aho-Corasick for fast substring
     pre-screening and Jaccard token-overlap for fuzzy matching (identical
     algorithm to ``sanctions.py``).

  2. Fallback path: If the Rust module is unavailable, falls back to the existing
     pure-Python ``SanctionsScreener``.  A ``UserWarning`` is emitted on startup.

Compliance note:
  The Rust screener matches the exact algorithm of ``sanctions.py`` — Jaccard
  token-overlap with threshold 0.8 — so there is no compliance regression from
  the Python implementation.  Both implementations share the same known
  compliance gap (no transliteration / phonetic matching).  See
  ``docs/c6_sanctions_audit.md`` for details.

Prometheus metrics (requires ``prometheus_client`` in the environment):
  ``c6_sanctions_screen_latency_seconds``  Histogram  screen() latency
  ``c6_sanctions_hits_total``             Counter    total hits returned
  ``c6_sanctions_misses_total``           Counter    total clean screens
  ``c6_sanctions_backend``               Info       "rust" or "python"
"""
from __future__ import annotations

import logging
import os
import warnings
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attempt to import the compiled Rust extension
# ---------------------------------------------------------------------------

_FORCE_PYTHON = os.environ.get("LIP_C6_FORCE_PYTHON", "0") == "1"

try:
    if _FORCE_PYTHON:
        raise ImportError("LIP_C6_FORCE_PYTHON=1 — forcing Python fallback")
    import lip_c6_rust_velocity as _rust  # type: ignore[import]

    _RUST_AVAILABLE = True
    logger.debug(
        "lip_c6_rust_velocity loaded: Rust-backed C6 sanctions screener active.",
    )
except ImportError:
    _rust = None  # type: ignore[assignment]
    _RUST_AVAILABLE = False
    warnings.warn(
        "lip_c6_rust_velocity Rust extension not found. "
        "Falling back to pure-Python C6 sanctions screening. "
        "Build the Rust extension with: "
        "cd lip/c6_aml_velocity/rust_velocity && maturin build --release && "
        "pip install target/wheels/*.whl",
        UserWarning,
        stacklevel=2,
    )

# ---------------------------------------------------------------------------
# Prometheus metrics (optional — gracefully absent)
# ---------------------------------------------------------------------------

try:
    from prometheus_client import Counter, Histogram, Info

    _sanc_latency = Histogram(
        "c6_sanctions_screen_latency_seconds",
        "C6 sanctions screen() latency in seconds",
        buckets=[0.0001, 0.0005, 0.001, 0.002, 0.005, 0.010, 0.050],
    )
    _sanc_hits = Counter(
        "c6_sanctions_hits_total",
        "Total C6 sanctions hits returned",
    )
    _sanc_misses = Counter(
        "c6_sanctions_misses_total",
        "Total C6 sanctions clean screens",
    )
    _sanc_backend = Info("c6_sanctions_backend", "C6 sanctions backend (rust or python)")
    _sanc_backend.info({"backend": "rust" if _RUST_AVAILABLE else "python"})
    _HAS_PROMETHEUS = True
except (ImportError, ValueError):
    # ValueError: Prometheus metric already registered (e.g. module reload in tests)
    _sanc_latency = _sanc_hits = _sanc_misses = None  # type: ignore[assignment]
    _HAS_PROMETHEUS = False


# ---------------------------------------------------------------------------
# _adapt_rust_hits — convert Rust dicts to SanctionsHit objects
# ---------------------------------------------------------------------------


def _adapt_rust_hits(raw_hits: list, py_screener) -> list:
    """Convert Rust screen() output (list of dicts) to SanctionsHit objects.

    The Rust screener returns ``list[dict]`` with keys: entity_name_hash,
    list_name, confidence, reference.  This adapter converts them to the same
    ``SanctionsHit`` dataclass used by the Python implementation.

    Args:
        raw_hits: List of dicts from ``PySanctionsScreener.screen()``.
        py_screener: A ``SanctionsScreener`` instance (used only for type info).
    """
    from lip.c6_aml_velocity.sanctions import SanctionsHit, SanctionsList

    hits = []
    for raw in raw_hits:
        try:
            list_name = SanctionsList(raw["list_name"])
        except ValueError:
            logger.warning("Unknown sanctions list name from Rust: %r", raw.get("list_name"))
            continue
        hits.append(SanctionsHit(
            entity_name_hash=raw["entity_name_hash"],
            list_name=list_name,
            confidence=float(raw["confidence"]),
            reference=raw["reference"],
        ))
    return hits


# ---------------------------------------------------------------------------
# Public API: RustSanctionsScreener (unified interface)
# ---------------------------------------------------------------------------


class RustSanctionsScreener:
    """Sanctions screener backed by Rust or pure Python.

    Presents the same interface as ``SanctionsScreener`` from ``sanctions.py``
    (``screen()``, ``is_clear()``, ``_load_lists()``), so it is a drop-in
    replacement for the C6 AML gate.

    When the Rust extension is available, screening runs in Rust with
    Aho-Corasick pre-filtering and Jaccard token-overlap — exact same
    algorithm as the Python implementation, with sub-millisecond latency.

    When unavailable, falls back to ``SanctionsScreener`` (pure Python).

    Args:
        lists_path: Optional filesystem path to a ``sanctions.json`` file.
                    When provided, the screener is loaded at construction.
                    When ``None``, uses mock entries (for tests / dev).
        threshold: Jaccard confidence threshold (default 0.8).
    """

    RUST_AVAILABLE: bool = _RUST_AVAILABLE

    def __init__(
        self,
        lists_path: Optional[str] = None,
        threshold: float = 0.8,
    ) -> None:
        self._threshold = threshold
        self._lists_path = lists_path

        if _RUST_AVAILABLE:
            self._rust_screener = _rust.PySanctionsScreener(threshold=threshold)
            self._py_screener = None
            self._load_rust(lists_path)
        else:
            from lip.c6_aml_velocity.sanctions import SanctionsScreener

            self._rust_screener = None
            self._py_screener = SanctionsScreener(lists_path=lists_path)

    def _load_rust(self, lists_path: Optional[str]) -> None:
        """Load sanctions entries into the Rust screener."""
        import json
        import os

        from lip.c6_aml_velocity.sanctions import MOCK_SANCTIONS_ENTRIES, SanctionsList

        if lists_path and os.path.exists(lists_path):
            with open(lists_path, encoding="utf-8") as f:
                data = json.load(f)
            entries = {
                SanctionsList.OFAC.value: data.get("OFAC", []),
                SanctionsList.EU.value: data.get("EU", []),
                SanctionsList.UN.value: data.get("UN", []),
            }
        else:
            if lists_path:
                logger.warning(
                    "Sanctions list file not found: %s; using mock data", lists_path
                )
            entries = {
                k.value: list(v) for k, v in MOCK_SANCTIONS_ENTRIES.items()
            }
        self._rust_screener.load(entries)

    def screen(self, entity_name: str, entity_id: Optional[str] = None) -> list:
        """Screen an entity name against all loaded sanctions lists.

        Returns a list of ``SanctionsHit`` objects (empty when entity is clear).

        Args:
            entity_name: Human-readable entity name to screen.
            entity_id: Optional entity identifier (currently unused).
        """
        import time

        t0 = time.monotonic()
        try:
            if _RUST_AVAILABLE:
                raw = list(self._rust_screener.screen(entity_name))
                hits = _adapt_rust_hits(raw, self._py_screener)
            else:
                hits = self._py_screener.screen(entity_name, entity_id)
        finally:
            elapsed = time.monotonic() - t0
            if _HAS_PROMETHEUS and _sanc_latency is not None:
                _sanc_latency.observe(elapsed)
                if hits:
                    _sanc_hits.inc(len(hits))
                else:
                    _sanc_misses.inc()

        return hits

    def is_clear(self, entity_name: str) -> bool:
        """Return True when the entity has no hits on any loaded list.

        Args:
            entity_name: Human-readable entity name to screen.
        """
        if _RUST_AVAILABLE:
            return self._rust_screener.is_clear(entity_name)
        return self._py_screener.is_clear(entity_name)

    def reload(self, lists_path: Optional[str] = None) -> None:
        """Reload sanctions list from disk (hot reload without restart).

        Args:
            lists_path: Path to updated ``sanctions.json``.  Defaults to the
                        path provided at construction time.
        """
        path = lists_path or self._lists_path
        if _RUST_AVAILABLE:
            self._load_rust(path)
        else:
            self._py_screener._load_lists(path) if path else None

    def flush(self) -> None:
        """Flush all loaded entries (for testing / reload workflows)."""
        if _RUST_AVAILABLE:
            self._rust_screener.flush()
        else:
            self._py_screener._lists.clear()

    def entry_count(self) -> int:
        """Return the number of loaded sanctions entries."""
        if _RUST_AVAILABLE:
            return self._rust_screener.entry_count()
        total = sum(len(v) for v in self._py_screener._lists.values())
        return total

    def get_rust_metrics(self) -> dict:
        """Return Rust-side atomic metric counters (Rust path only; {} on Python path)."""
        if _RUST_AVAILABLE:
            return dict(self._rust_screener.get_metrics())
        return {}

    def health_check(self) -> dict:
        """Return health dict with backend and entry count."""
        if _RUST_AVAILABLE:
            return dict(self._rust_screener.health_check())
        return {
            "ok": True,
            "entry_count": self.entry_count(),
            "backend": "python",
        }
