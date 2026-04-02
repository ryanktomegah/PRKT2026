// main.go — Entry point for the C7 Go offer router service.
//
// Wires up configuration, kill switch, metrics, and gRPC server.
// Blocks until SIGTERM/SIGINT, then shuts down gracefully.
package main

import (
	"log/slog"
	"net"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))

	cfg, err := LoadConfig()
	if err != nil {
		log.Error("config error", "err", err)
		os.Exit(1)
	}

	log.Info("c7 go offer router starting",
		"grpc_addr", cfg.GRPCAddr,
		"metrics_addr", cfg.MetricsAddr,
		"max_concurrent_offers", cfg.MaxConcurrentOffers,
		"kill_switch_shm", cfg.KillSwitchSHMPath,
	)

	// Kill switch reader — fail-closed on SHM absence
	ks := NewKillSwitchReader(cfg.KillSwitchSHMPath, log)
	ks.StartMonitor()
	defer ks.Stop()

	// Prometheus metrics endpoint
	metrics := NewMetrics()
	StartMetricsServer(cfg.MetricsAddr)
	log.Info("metrics server started", "addr", cfg.MetricsAddr)

	// gRPC listener
	lis, err := net.Listen("tcp", cfg.GRPCAddr)
	if err != nil {
		log.Error("listen failed", "addr", cfg.GRPCAddr, "err", err)
		os.Exit(1)
	}

	srv := NewOfferRouterServer(cfg, ks, metrics, log)

	// Graceful shutdown on SIGTERM / SIGINT
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)
	go func() {
		sig := <-sigCh
		log.Info("received signal, shutting down", "signal", sig)
		srv.Shutdown()
	}()

	log.Info("gRPC server ready", "addr", cfg.GRPCAddr)
	if err := srv.Serve(lis); err != nil {
		log.Error("gRPC server error", "err", err)
		os.Exit(1)
	}
	log.Info("c7 go offer router stopped")
}
