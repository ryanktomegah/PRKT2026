// metrics_noop.go — No-op metric implementations for unit testing.
//
// These stubs satisfy the Counter, Gauge, Observer, and ObserverVec interfaces
// defined in metrics.go without registering against any prometheus registry.
// Used exclusively in server_test.go via newNoopMetrics().
package main

// noopCounter is a Counter that discards all observations.
type noopCounter struct{}

func (noopCounter) Inc()        {}
func (noopCounter) Add(float64) {}

// noopGauge is a Gauge that discards all observations.
type noopGauge struct{}

func (noopGauge) Set(float64) {}
func (noopGauge) Inc()        {}
func (noopGauge) Dec()        {}

// noopObserver is an Observer that discards all observations.
type noopObserver struct{}

func (noopObserver) Observe(float64) {}

// noopObserverVec is an ObserverVec that returns noopObserver for any label set.
type noopObserverVec struct{}

func (noopObserverVec) WithLabelValues(_ ...string) Observer { return noopObserver{} }

// newNoopMetrics returns a Metrics wired with all noop implementations.
// Safe to call multiple times in the same test binary.
func newNoopMetrics() *Metrics {
	return &Metrics{
		OffersTriggered:  noopCounter{},
		OffersAccepted:   noopCounter{},
		OffersRejected:   noopCounter{},
		OffersExpired:    noopCounter{},
		OffersCancelled:  noopCounter{},
		ActiveOffers:     noopGauge{},
		KillSwitchBlocks: noopCounter{},
		OfferLatency:     noopObserverVec{},
		ExpiryLatency:    noopObserver{},
		GRPCDuration:     noopObserverVec{},
	}
}
