// config.go — Environment-driven configuration for the C7 Go offer router service.
//
// All settings are read from environment variables so the service integrates
// with the existing Python-managed configuration layer. Hot-path timing and
// concurrency settings live here; per-corridor policy overrides live in Python.
package main

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

// Config holds all runtime configuration for the Go offer router service.
type Config struct {
	// gRPC server listen address (default :50057)
	GRPCAddr string

	// Prometheus metrics listen address (default :9091)
	MetricsAddr string

	// Maximum number of concurrent in-flight offer goroutines.
	// 0 = unlimited (default, bounded by system resources).
	MaxConcurrentOffers int

	// Default offer expiry window applied when expires_at is not provided
	// in the TriggerOffer request (default 120s — Class A window).
	DefaultExpirySeconds int

	// Kill switch shared memory path (default /dev/shm/lip_kill_switch).
	KillSwitchSHMPath string

	// gRPC log level: "debug", "info", "warn", "error" (default "info")
	LogLevel string

	// Graceful shutdown timeout (default 30s)
	ShutdownTimeout time.Duration

	// gRPC max message size in bytes (default 4 MiB)
	GRPCMaxMsgSize int

	// TTL for resolved offer entries before eviction (default 1h).
	// Keeps the resolved map bounded for long-running processes.
	ResolvedTTL time.Duration
}

// LoadConfig reads all settings from environment variables, applying
// production-safe defaults. Returns an error for invalid numeric values.
func LoadConfig() (*Config, error) {
	cfg := &Config{
		GRPCAddr:             getEnv("C7_GRPC_ADDR", ":50057"),
		MetricsAddr:          getEnv("C7_METRICS_ADDR", ":9091"),
		KillSwitchSHMPath:    getEnv("C7_KILL_SWITCH_SHM_PATH", "/dev/shm/lip_kill_switch"),
		LogLevel:             getEnv("C7_LOG_LEVEL", "info"),
		GRPCMaxMsgSize:       4 * 1024 * 1024,
		DefaultExpirySeconds: 120,
		MaxConcurrentOffers:  0,
		ShutdownTimeout:      30 * time.Second,
		ResolvedTTL:          1 * time.Hour,
	}

	if v := os.Getenv("C7_MAX_CONCURRENT_OFFERS"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			return nil, fmt.Errorf("C7_MAX_CONCURRENT_OFFERS must be an integer: %w", err)
		}
		if n < 0 {
			return nil, fmt.Errorf("C7_MAX_CONCURRENT_OFFERS must be >= 0, got %d", n)
		}
		cfg.MaxConcurrentOffers = n
	}

	if v := os.Getenv("C7_DEFAULT_EXPIRY_SECONDS"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			return nil, fmt.Errorf("C7_DEFAULT_EXPIRY_SECONDS must be an integer: %w", err)
		}
		if n <= 0 {
			return nil, fmt.Errorf("C7_DEFAULT_EXPIRY_SECONDS must be > 0, got %d", n)
		}
		cfg.DefaultExpirySeconds = n
	}

	if v := os.Getenv("C7_SHUTDOWN_TIMEOUT_SECONDS"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			return nil, fmt.Errorf("C7_SHUTDOWN_TIMEOUT_SECONDS must be an integer: %w", err)
		}
		if n <= 0 {
			return nil, fmt.Errorf("C7_SHUTDOWN_TIMEOUT_SECONDS must be > 0, got %d", n)
		}
		cfg.ShutdownTimeout = time.Duration(n) * time.Second
	}

	if v := os.Getenv("C7_GRPC_MAX_MSG_SIZE"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			return nil, fmt.Errorf("C7_GRPC_MAX_MSG_SIZE must be an integer: %w", err)
		}
		if n <= 0 {
			return nil, fmt.Errorf("C7_GRPC_MAX_MSG_SIZE must be > 0, got %d", n)
		}
		cfg.GRPCMaxMsgSize = n
	}

	return cfg, nil
}

func getEnv(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}
