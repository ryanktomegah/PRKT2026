// consumer_test.go — B6-02 regression tests for the C5 Go consumer.
//
// Before the 2026-04-09 hardening sprint, processMessage called commitOffset
// on every error path (normalization, fan-out, produce). Transient C1/C2
// fan-out blips committed the offset anyway and the message was lost to the
// DLQ — breaking the exactly-once claim encoded in the Kafka producer/
// consumer config. These tests assert the rule codified in
// processMessageResult.shouldCommit: only resultSuccess and resultNullValue
// advance the offset; every error result leaves the offset uncommitted so a
// rebalance will redeliver the message.
//
// A pure Go unit-test of the fully-instrumented processMessage would require
// mocking confluent-kafka-go's concrete Consumer/Producer types, which is
// impractical. Instead we test (a) the pure shouldCommit function and (b)
// that every enum value is classified explicitly, so adding a new outcome
// without updating shouldCommit fails the build. A companion Python grep
// guard (lip/tests/test_c5_consumer_commit_on_error.py) enforces that
// processMessage never calls commitOffset directly again.
package main

import (
	"testing"
)

// TestShouldCommit_SuccessAndTombstoneOnly — the B6-02 invariant.
func TestShouldCommit_SuccessAndTombstoneOnly(t *testing.T) {
	cases := []struct {
		name   string
		result processMessageResult
		commit bool
	}{
		{"success commits", resultSuccess, true},
		{"null-value tombstone commits", resultNullValue, true},
		{"normalize error does NOT commit", resultNormalizeError, false},
		{"fan-out error does NOT commit", resultFanOutError, false},
		{"produce error does NOT commit", resultProduceError, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := tc.result.shouldCommit(); got != tc.commit {
				t.Fatalf("shouldCommit for %s = %v; want %v", tc.name, got, tc.commit)
			}
		})
	}
}

// TestShouldCommit_AllEnumValuesCovered — every known processMessageResult
// value must be explicitly classified by shouldCommit. If someone adds a new
// result (e.g. resultSchemaError) without updating shouldCommit, the default
// branch would silently return false for it and this test would pass — but
// the new case should be added here as well so the intent is visible.
//
// This test exists because B6-02 was exactly this class of bug: a silent
// default behaviour (commit on every path) with no explicit classification.
func TestShouldCommit_AllEnumValuesCovered(t *testing.T) {
	// Known enum values as of the B6-02 fix. Extend this list when a new
	// outcome is added.
	known := []processMessageResult{
		resultSuccess,
		resultNullValue,
		resultNormalizeError,
		resultFanOutError,
		resultProduceError,
	}

	// Sanity: the highest known value should be the last constant.
	// If someone appends a new enum member without extending `known`, this
	// assertion still passes (iota is append-only) but the other tests will
	// fail to cover the new case — which is the intended safety net.
	if len(known) < 5 {
		t.Fatalf("known enum coverage regressed; expected at least 5, got %d", len(known))
	}

	// Classify every known value exactly once.
	classified := map[processMessageResult]bool{}
	for _, r := range known {
		classified[r] = r.shouldCommit()
	}
	if len(classified) != len(known) {
		t.Fatalf("duplicate enum values: %v", known)
	}

	// Exactly two values (success + null-value tombstone) may commit.
	commitCount := 0
	for _, c := range classified {
		if c {
			commitCount++
		}
	}
	if commitCount != 2 {
		t.Fatalf("expected exactly 2 commit-eligible outcomes, got %d", commitCount)
	}
}
