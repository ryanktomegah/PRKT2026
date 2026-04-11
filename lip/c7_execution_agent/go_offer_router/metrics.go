// metrics.go — Prometheus metrics for the C7 Go offer router service.
//
// Exposes a /metrics HTTP endpoint on MetricsAddr (default :9091).
// Tracks per-offer lifecycle counters, concurrency gauge, latency histograms,
// and kill-switch block events.
//
// Uses interface types so tests can inject noop implementations without
// registering against the global prometheus registry.
package main

import (
	"log/slog"
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// ─────────────────────────────────────────────────────────────────────────────
// Interfaces — allow test injection of noop implementations
// ─────────────────────────────────────────────────────────────────────────────

// Counter is a prometheus counter subset used by the offer router.
type Counter interface {
	Inc()
	Add(float64)
}

// Gauge is a prometheus gauge subset used by the offer router.
type Gauge interface {
	Set(float64)
	Inc()
	Dec()
}

// Observer wraps a single Observe call (Histogram, Summary, etc.)
type Observer interface {
	Observe(float64)
}

// ObserverVec wraps a labelled observer (replaces *prometheus.HistogramVec).
type ObserverVec interface {
	WithLabelValues(lvs ...string) Observer
}

// ─────────────────────────────────────────────────────────────────────────────
// Metrics struct
// ─────────────────────────────────────────────────────────────────────────────

// Metrics holds all observability instruments for the C7 Go offer router.
type Metrics struct {
	// Lifecycle counters — one label value per terminal outcome
	OffersTriggered  Counter
	OffersAccepted   Counter
	OffersRejected   Counter
	OffersExpired    Counter
	OffersCancelled  Counter

	// Concurrency gauge — tracks live goroutines
	ActiveOffers Gauge

	// Kill switch guard
	KillSwitchBlocks Counter

	// Latency: trigger→resolution, labelled by outcome
	OfferLatency ObserverVec

	// Expiry skew: (actual expiry time) - (scheduled ExpiresAt)
	ExpiryLatency Observer

	// gRPC handler latency by method
	GRPCDuration ObserverVec
}

// ─────────────────────────────────────────────────────────────────────────────
// histogramVecAdapter wraps *prometheus.HistogramVec to satisfy ObserverVec
// ─────────────────────────────────────────────────────────────────────────────

type histogramVecAdapter struct {
	hv *prometheus.HistogramVec
}

func (a *histogramVecAdapter) WithLabelValues(lvs ...string) Observer {
	return a.hv.WithLabelValues(lvs...)
}

// ─────────────────────────────────────────────────────────────────────────────
// NewMetrics — registers instruments against the global prometheus registry
// ─────────────────────────────────────────────────────────────────────────────

// NewMetrics registers and returns all Prometheus instruments.
func NewMetrics() *Metrics {
	// Offer lifecycle latency buckets: 1ms–600s (covers Class A 3d + Class C 21d
	// windows with fine resolution in the 0–5ms hot-path region).
	latencyBuckets := []float64{
		0.001, 0.005, 0.010, 0.050, 0.100, 0.500,
		1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0,
	}

	// gRPC handler buckets: sub-millisecond precision for the hot path
	grpcBuckets := []float64{
		0.0001, 0.0005, 0.001, 0.005, 0.010, 0.050, 0.094, 0.200, 1.000,
	}

	// Expiry skew buckets: signed delta in seconds (negative=early, positive=late)
	expiryBuckets := []float64{
		-0.100, -0.010, -0.001, 0.0, 0.001, 0.010, 0.100, 1.000, 5.000,
	}

	return &Metrics{
		OffersTriggered: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c7_go_offers_triggered_total",
			Help: "Total new loan offers registered with the Go offer router",
		}),
		OffersAccepted: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c7_go_offers_accepted_total",
			Help: "Total loan offers accepted by ELO treasury",
		}),
		OffersRejected: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c7_go_offers_rejected_total",
			Help: "Total loan offers rejected by ELO treasury",
		}),
		OffersExpired: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c7_go_offers_expired_total",
			Help: "Total loan offers that expired before ELO responded",
		}),
		OffersCancelled: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c7_go_offers_cancelled_total",
			Help: "Total loan offers cancelled by upstream (e.g. kill switch)",
		}),
		ActiveOffers: promauto.NewGauge(prometheus.GaugeOpts{
			Name: "c7_go_active_offers",
			Help: "Current number of in-flight offer goroutines",
		}),
		KillSwitchBlocks: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c7_go_kill_switch_blocks_total",
			Help: "Total TriggerOffer calls blocked by the kill switch",
		}),
		OfferLatency: &histogramVecAdapter{
			hv: promauto.NewHistogramVec(prometheus.HistogramOpts{
				Name:    "c7_go_offer_latency_seconds",
				Help:    "Wall time from TriggerOffer to terminal outcome",
				Buckets: latencyBuckets,
			}, []string{"outcome"}),
		},
		ExpiryLatency: promauto.NewHistogram(prometheus.HistogramOpts{
			Name:    "c7_go_expiry_latency_seconds",
			Help:    "Signed delta between actual goroutine-exit time and scheduled ExpiresAt (positive=late)",
			Buckets: expiryBuckets,
		}),
		GRPCDuration: &histogramVecAdapter{
			hv: promauto.NewHistogramVec(prometheus.HistogramOpts{
				Name:    "c7_go_grpc_duration_seconds",
				Help:    "gRPC handler latency by method",
				Buckets: grpcBuckets,
			}, []string{"method"}),
		},
	}
}

// StartMetricsServer starts the Prometheus HTTP endpoint in a background
// goroutine. The server runs until the process exits.
// B4-13: Uses log/slog for error reporting instead of panic so a metrics
// endpoint failure degrades observability without crashing the offer router.
func StartMetricsServer(addr string) {
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok\n"))
	})
	go func() {
		if err := http.ListenAndServe(addr, mux); err != nil && err != http.ErrServerClosed {
			// B4-13: Log error and return rather than panicking — a metrics server
			// failure must not crash the offer router. Observability degrades
			// gracefully; the router continues processing offers.
			slog.Error("c7 metrics server failed — metrics endpoint unavailable",
				"addr", addr, "err", err)
		}
	}()
}
