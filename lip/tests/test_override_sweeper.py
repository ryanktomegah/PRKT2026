"""Tests for GAP-08: Override expiry sweeper."""
from __future__ import annotations

import time

from lip.c7_execution_agent.human_override import HumanOverrideInterface
from lip.c7_execution_agent.override_sweeper import OverrideSweeper


class TestOverrideSweeper:
    def test_sweep_no_pending(self):
        override = HumanOverrideInterface(timeout_seconds=300)
        sweeper = OverrideSweeper(override)
        assert sweeper.sweep_once() == 0

    def test_sweep_resolves_expired(self):
        override = HumanOverrideInterface(timeout_seconds=0.05, timeout_action="DECLINE")
        req = override.request_override(
            uetr="test-uetr",
            original_decision="OFFER",
            ai_confidence=0.5,
            reason="test",
        )
        time.sleep(0.1)
        sweeper = OverrideSweeper(override)
        resolved = sweeper.sweep_once()
        assert resolved == 1
        assert sweeper.resolved_count == 1
        assert not override.is_pending(req.request_id)

    def test_sweep_does_not_resolve_active(self):
        override = HumanOverrideInterface(timeout_seconds=300)
        override.request_override(
            uetr="test-uetr",
            original_decision="OFFER",
            ai_confidence=0.5,
            reason="test",
        )
        sweeper = OverrideSweeper(override)
        resolved = sweeper.sweep_once()
        assert resolved == 0

    def test_sweep_with_offer_action(self):
        override = HumanOverrideInterface(timeout_seconds=0.05, timeout_action="OFFER")
        override.request_override(
            uetr="test-uetr",
            original_decision="OFFER",
            ai_confidence=0.5,
            reason="test",
        )
        time.sleep(0.1)
        sweeper = OverrideSweeper(override)
        resolved = sweeper.sweep_once()
        assert resolved == 1

    def test_sweep_multiple_expired(self):
        override = HumanOverrideInterface(timeout_seconds=0.05)
        for i in range(3):
            override.request_override(
                uetr=f"uetr-{i}",
                original_decision="OFFER",
                ai_confidence=0.5,
                reason="test",
            )
        time.sleep(0.1)
        sweeper = OverrideSweeper(override)
        resolved = sweeper.sweep_once()
        assert resolved == 3

    def test_start_stop_lifecycle(self):
        override = HumanOverrideInterface(timeout_seconds=300)
        sweeper = OverrideSweeper(override, sweep_interval_seconds=0.1)
        sweeper.start()
        assert sweeper.is_running
        sweeper.stop()
        assert not sweeper.is_running

    def test_notification_on_expire(self):
        delivered = []

        class FakeNotification:
            def notify(self, event_type, uetr, payload=None, licensee_id=""):
                delivered.append({"event_type": event_type, "uetr": uetr})

        override = HumanOverrideInterface(timeout_seconds=0.05, timeout_action="DECLINE")
        override.request_override(
            uetr="test-uetr",
            original_decision="OFFER",
            ai_confidence=0.5,
            reason="test",
        )
        time.sleep(0.1)
        sweeper = OverrideSweeper(override, notification_service=FakeNotification())
        sweeper.sweep_once()
        assert len(delivered) == 1
        assert delivered[0]["uetr"] == "test-uetr"
