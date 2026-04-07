// metrics.go — Prometheus metrics for the C5 Go Kafka consumer.
//
// Exposes a /metrics HTTP endpoint on MetricsAddr (default :9090).
// Mirrors the Python PaymentEventWorker stats dict with additional Go-specific
// gauges (goroutine count, GC pause frequency).
package main

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// Metrics holds all Prometheus instruments for the C5 Go consumer.
type Metrics struct {
	MessagesConsumed  prometheus.Counter
	MessagesProduced  prometheus.Counter
	ProcessingErrors  prometheus.Counter
	DLQRouted         prometheus.Counter
	ProduceErrors     prometheus.Counter
	IngestionLatency  prometheus.Histogram
	NormalizeDuration prometheus.Histogram
	GRPCDuration      *prometheus.HistogramVec
	GRPCUpstreamErrors *prometheus.CounterVec
	ActiveWorkers     prometheus.Gauge
}

// NewMetrics registers and returns all Prometheus instruments.
// Panics if registration fails (indicates duplicate registration in tests).
func NewMetrics() *Metrics {
	// 2ms ingestion latency budget (spec requirement). Buckets cover the full
	// 0–94ms SLO range with fine resolution in the 0–5ms critical region.
	ingestionBuckets := []float64{
		0.0005, 0.001, 0.002, 0.005,
		0.010, 0.020, 0.050, 0.094,
		0.200, 0.500, 1.000,
	}

	return &Metrics{
		MessagesConsumed: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c5_go_messages_consumed_total",
			Help: "Total Kafka messages consumed from lip.payment.events",
		}),
		MessagesProduced: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c5_go_messages_produced_total",
			Help: "Total messages produced to lip.failure.predictions",
		}),
		ProcessingErrors: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c5_go_processing_errors_total",
			Help: "Total messages that failed normalization or pipeline call",
		}),
		DLQRouted: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c5_go_dlq_routed_total",
			Help: "Total messages routed to lip.dead.letter",
		}),
		ProduceErrors: promauto.NewCounter(prometheus.CounterOpts{
			Name: "c5_go_produce_errors_total",
			Help: "Total produce failures (after all retries)",
		}),
		IngestionLatency: promauto.NewHistogram(prometheus.HistogramOpts{
			Name:    "c5_go_ingestion_latency_seconds",
			Help:    "End-to-end ingestion latency (consume → produce). Budget: 2ms.",
			Buckets: ingestionBuckets,
		}),
		NormalizeDuration: promauto.NewHistogram(prometheus.HistogramOpts{
			Name:    "c5_go_normalize_duration_seconds",
			Help:    "Time spent in Normalizer.Normalize() per message",
			Buckets: prometheus.DefBuckets,
		}),
		GRPCDuration: promauto.NewHistogramVec(prometheus.HistogramOpts{
			Name:    "c5_go_grpc_duration_seconds",
			Help:    "gRPC call duration by upstream service (c1, c2, c6)",
			Buckets: ingestionBuckets,
		}, []string{"service"}),
		GRPCUpstreamErrors: promauto.NewCounterVec(prometheus.CounterOpts{
			Name: "c5_go_grpc_upstream_errors_total",
			Help: "Total gRPC errors from upstream services (c1, c2, c6). Non-zero rate indicates systemic outage.",
		}, []string{"service"}),
		ActiveWorkers: promauto.NewGauge(prometheus.GaugeOpts{
			Name: "c5_go_active_workers",
			Help: "Number of active consumer goroutines",
		}),
	}
}

// StartMetricsServer starts the Prometheus HTTP endpoint in a background
// goroutine. The server runs until the process exits.
func StartMetricsServer(addr string) {
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})
	go func() {
		if err := http.ListenAndServe(addr, mux); err != nil && err != http.ErrServerClosed {
			panic("metrics server failed: " + err.Error())
		}
	}()
}
