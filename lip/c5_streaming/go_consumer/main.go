// main.go — Entry point for the C5 Go Kafka consumer service.
//
// This service is a drop-in replacement for the Python PaymentEventWorker in
// kafka_worker.py. It reads from lip.payment.events, normalizes events using
// the same field semantics as the Python EventNormalizer, fans out to C1/C2/C6
// via gRPC, and produces results to lip.failure.predictions.
//
// Usage:
//
//	./c5-go-consumer
//
// All configuration is via environment variables (see config.go).
// Prometheus metrics are served at METRICS_ADDR (default :9090/metrics).
//
// A/B deployment: both this service and the Python worker can run simultaneously
// against different consumer groups (KAFKA_GROUP_ID). Canary traffic routing is
// controlled via Kafka partition assignment or a load balancer upstream.
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	// Structured logging
	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(log)

	log.Info("LIP C5 Go Kafka consumer starting",
		"version", "1.0.0",
		"component", "c5-go-consumer",
	)

	// Load config from environment
	cfg, err := LoadConfig()
	if err != nil {
		log.Error("Config load failed", "error", err)
		os.Exit(1)
	}

	if cfg.LogLevel == "debug" {
		log = slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
			Level: slog.LevelDebug,
		}))
		slog.SetDefault(log)
	}

	// Start Prometheus metrics server
	StartMetricsServer(cfg.MetricsAddr)
	log.Info("Metrics server started", "addr", cfg.MetricsAddr)

	metrics := NewMetrics()

	// Dial gRPC upstreams (C1, C2, C6)
	// In dry-run mode, create a no-op client so tests don't need live services.
	var grpcClient *GRPCClient
	if cfg.DryRun {
		grpcClient = &GRPCClient{timeout: cfg.GRPCTimeout}
		log.Info("Dry-run mode: gRPC client is a no-op stub")
	} else {
		grpcClient, err = NewGRPCClient(cfg.GRPCC1Addr, cfg.GRPCC2Addr, cfg.GRPCC6Addr, cfg.GRPCTimeout)
		if err != nil {
			log.Error("gRPC client init failed", "error", err)
			os.Exit(1)
		}
		defer grpcClient.Close()
		log.Info("gRPC clients connected",
			"c1", cfg.GRPCC1Addr,
			"c2", cfg.GRPCC2Addr,
			"c6", cfg.GRPCC6Addr,
		)
	}

	// Create Kafka consumer
	consumer, err := NewConsumer(cfg, grpcClient, metrics, log)
	if err != nil {
		log.Error("Kafka consumer init failed", "error", err)
		os.Exit(1)
	}

	// Context cancellation on SIGTERM / SIGINT
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer cancel()

	log.Info("C5 Go consumer ready — listening for SIGTERM/SIGINT")

	if err := consumer.Run(ctx); err != nil {
		log.Error("Consumer run error", "error", err)
		os.Exit(1)
	}

	log.Info("C5 Go consumer exited cleanly")
}
