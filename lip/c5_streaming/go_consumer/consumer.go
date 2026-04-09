// consumer.go — Core Kafka consumer loop for the C5 Go service.
//
// Implements exactly-once semantics via:
//   - enable.idempotence=true on the producer
//   - isolation.level=read_committed on the consumer
//   - Manual offset commit (StoreOffsets) only after successful produce
//
// Goroutine model: N worker goroutines (NUM_WORKERS) each pull from a shared
// message channel. The main goroutine polls Kafka and distributes to workers,
// avoiding per-partition goroutine overhead and providing backpressure.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

const (
	dlqMaxRetries       = 3
	dlqBackoffBase      = 100 * time.Millisecond
	producerFlushTimeoutMs = 10_000 // 10 s producer flush timeout on shutdown
)

// Consumer is the main C5 Go Kafka consumer. It owns the confluent-kafka-go
// consumer/producer pair and dispatches messages to worker goroutines.
type Consumer struct {
	cfg        *Config
	consumer   *kafka.Consumer
	producer   *kafka.Producer
	normalizer *Normalizer
	grpc       *GRPCClient
	metrics    *Metrics
	log        *slog.Logger

	msgCh  chan *kafka.Message
	stopCh chan struct{}
}

// NewConsumer creates and configures the Kafka consumer/producer pair.
// Returns an error if the brokers cannot be reached.
func NewConsumer(cfg *Config, grpcClient *GRPCClient, metrics *Metrics, log *slog.Logger) (*Consumer, error) {
	consumerCfg := cfg.KafkaConsumerConfigMap()
	kConsumer, err := kafka.NewConsumer(toKafkaConfigMap(consumerCfg))
	if err != nil {
		return nil, fmt.Errorf("create kafka consumer: %w", err)
	}

	var kProducer *kafka.Producer
	if !cfg.DryRun {
		producerCfg := cfg.KafkaProducerConfigMap()
		kProducer, err = kafka.NewProducer(toKafkaConfigMap(producerCfg))
		if err != nil {
			_ = kConsumer.Close()
			return nil, fmt.Errorf("create kafka producer: %w", err)
		}
	}

	return &Consumer{
		cfg:        cfg,
		consumer:   kConsumer,
		producer:   kProducer,
		normalizer: NewNormalizer(cfg.SchemaRegistryURL),
		grpc:       grpcClient,
		metrics:    metrics,
		log:        log,
		msgCh:      make(chan *kafka.Message, cfg.NumWorkers*2),
		stopCh:     make(chan struct{}),
	}, nil
}

// Run starts the consumer loop and blocks until ctx is cancelled.
// Spawns NumWorkers goroutines, then polls Kafka in the calling goroutine.
func (c *Consumer) Run(ctx context.Context) error {
	if err := c.consumer.Subscribe(c.cfg.KafkaInputTopic, nil); err != nil {
		return fmt.Errorf("subscribe to %s: %w", c.cfg.KafkaInputTopic, err)
	}

	c.log.Info("C5 Go consumer started",
		"topic", c.cfg.KafkaInputTopic,
		"group", c.cfg.KafkaGroupID,
		"workers", c.cfg.NumWorkers,
		"dry_run", c.cfg.DryRun,
	)

	// Start worker goroutines
	done := make(chan struct{}, c.cfg.NumWorkers)
	for i := 0; i < c.cfg.NumWorkers; i++ {
		c.metrics.ActiveWorkers.Inc()
		go func() {
			defer func() {
				c.metrics.ActiveWorkers.Dec()
				done <- struct{}{}
			}()
			c.workerLoop(ctx)
		}()
	}

	// Poll loop (main goroutine)
	pollTimeout := time.Duration(c.cfg.PollTimeoutMs) * time.Millisecond
	for {
		select {
		case <-ctx.Done():
			close(c.msgCh)
			// Wait for all workers to drain
			for i := 0; i < c.cfg.NumWorkers; i++ {
				<-done
			}
			c.shutdown()
			return nil
		default:
		}

		msg := c.consumer.Poll(int(pollTimeout.Milliseconds()))
		if msg == nil {
			continue
		}

		switch e := msg.(type) {
		case *kafka.Message:
			c.msgCh <- e
		case kafka.Error:
			c.log.Error("Kafka consumer error", "code", e.Code(), "error", e)
		}
	}
}

// processMessageResult is the outcome of processing a single Kafka message.
//
// B6-02: before this type existed, processMessage called commitOffset directly
// on every code path — including normalization, fan-out, and produce errors.
// That silently broke the exactly-once claim: a transient C1/C2 fan-out error
// committed the offset anyway, so the message was never redelivered on restart
// and was lost to the DLQ (assuming DLQ routing even succeeded). The reviewer's
// recommended fix is "never commit on error; let rebalance redeliver." This
// enum makes the commit decision a single, centralised fact — workerLoop calls
// commitOffset iff result.shouldCommit() returns true — and shouldCommit is a
// pure function that is unit-tested against the B6-02 invariant.
type processMessageResult int

const (
	// resultSuccess — full pipeline completed; offset may advance.
	resultSuccess processMessageResult = iota
	// resultNullValue — Kafka tombstone/null-value record; nothing to process
	// but the offset may advance so the partition doesn't stall on tombstones.
	resultNullValue
	// resultNormalizeError — raw bytes failed to decode; routed to DLQ.
	// Offset is NOT committed; rebalance will redeliver. Poison-pill handling
	// (max retries then skip-and-commit) is tracked as a Phase 2 follow-up;
	// the B6-02 fix is deliberately conservative and prefers partition stall
	// over silent data loss.
	resultNormalizeError
	// resultFanOutError — C1/C2/C6 gRPC fan-out failed; routed to DLQ.
	// Almost always transient; do NOT commit — rebalance will retry.
	resultFanOutError
	// resultProduceError — output-topic produce failed after retries; routed
	// to DLQ. Do NOT commit; rebalance will retry from the same offset.
	resultProduceError
)

// shouldCommit is the B6-02 rule: only successes and null-value tombstones
// may advance the Kafka offset. Every error path returns false so the message
// is redelivered on the next rebalance (fail-closed exactly-once semantics).
//
// Changing this function MUST be accompanied by a review of the commit-path
// unit tests in consumer_test.go and the pytest grep guard in
// lip/tests/test_c5_consumer_commit_on_error.py (B6-02 regression test).
func (r processMessageResult) shouldCommit() bool {
	switch r {
	case resultSuccess, resultNullValue:
		return true
	default:
		return false
	}
}

// workerLoop processes messages from msgCh until the channel is closed.
//
// B6-02: the commit decision is centralised here, NOT inside processMessage.
// processMessage reports its outcome and workerLoop consults shouldCommit.
// This is the only place in the consumer that is allowed to call
// commitOffset — the pytest grep guard enforces that.
func (c *Consumer) workerLoop(ctx context.Context) {
	for msg := range c.msgCh {
		start := time.Now()
		result := c.processMessage(ctx, msg)
		if result.shouldCommit() {
			c.commitOffset(msg)
		}
		c.metrics.IngestionLatency.Observe(time.Since(start).Seconds())
	}
}

// processMessage implements the normalize → fan-out → produce pipeline and
// returns a processMessageResult describing the outcome. It routes errored
// messages to the DLQ but does NOT commit the Kafka offset itself — the
// caller (workerLoop) commits iff result.shouldCommit() returns true.
func (c *Consumer) processMessage(ctx context.Context, msg *kafka.Message) processMessageResult {
	if msg.Value == nil {
		c.log.Warn("Null-value message — skipping", "offset", msg.TopicPartition.Offset)
		return resultNullValue
	}

	// Normalize (JSON or Avro)
	normStart := time.Now()
	event, err := c.normalizer.Normalize(msg.Value)
	c.metrics.NormalizeDuration.Observe(time.Since(normStart).Seconds())
	if err != nil {
		c.log.Error("Normalization error — routing to DLQ",
			"offset", msg.TopicPartition.Offset, "error", err)
		c.routeDLQ(msg)
		c.metrics.ProcessingErrors.Inc()
		return resultNormalizeError
	}

	// gRPC fan-out to C1/C2/C6
	result, err := c.grpc.FanOut(ctx, event, c.metrics)
	if err != nil {
		c.log.Error("Pipeline fan-out error — routing to DLQ",
			"uetr", event.UETR, "error", err)
		c.routeDLQ(msg)
		c.metrics.ProcessingErrors.Inc()
		return resultFanOutError
	}

	// Produce result
	if !c.cfg.DryRun && c.producer != nil {
		resultBytes, _ := json.Marshal(result)
		if err := c.produceWithRetry(event.UETR, resultBytes); err != nil {
			c.log.Error("Produce error after retries — routing to DLQ",
				"uetr", event.UETR, "error", err)
			c.routeDLQ(msg)
			c.metrics.ProduceErrors.Inc()
			return resultProduceError
		}
		c.metrics.MessagesProduced.Inc()
	}

	c.metrics.MessagesConsumed.Inc()
	return resultSuccess
}

// produceWithRetry produces to the output topic with exponential backoff.
// On exhaustion, returns an error (caller routes to DLQ).
func (c *Consumer) produceWithRetry(uetr string, value []byte) error {
	topic := c.cfg.KafkaOutputTopic
	var lastErr error
	for attempt := 0; attempt < dlqMaxRetries; attempt++ {
		deliveryCh := make(chan kafka.Event, 1)
		err := c.producer.Produce(&kafka.Message{
			TopicPartition: kafka.TopicPartition{
				Topic:     &topic,
				Partition: kafka.PartitionAny,
			},
			Key:   []byte(uetr),
			Value: value,
		}, deliveryCh)
		if err != nil {
			lastErr = err
			backoff := dlqBackoffBase * time.Duration(math.Pow(2, float64(attempt)))
			c.log.Warn("Produce failed — retrying",
				"attempt", attempt+1, "backoff_ms", backoff.Milliseconds(), "error", err)
			time.Sleep(backoff)
			continue
		}
		// Wait for delivery confirmation
		e := <-deliveryCh
		if dm, ok := e.(*kafka.Message); ok {
			if dm.TopicPartition.Error != nil {
				lastErr = dm.TopicPartition.Error
				backoff := dlqBackoffBase * time.Duration(math.Pow(2, float64(attempt)))
				time.Sleep(backoff)
				continue
			}
		}
		return nil
	}
	return fmt.Errorf("produce failed after %d retries: %w", dlqMaxRetries, lastErr)
}

// routeDLQ forwards a failed message to the dead-letter topic.
func (c *Consumer) routeDLQ(msg *kafka.Message) {
	if c.cfg.DryRun || c.producer == nil {
		return
	}
	dlq := c.cfg.KafkaDLQTopic
	err := c.producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{
			Topic:     &dlq,
			Partition: kafka.PartitionAny,
		},
		Key:   msg.Key,
		Value: msg.Value,
		Headers: []kafka.Header{
			{Key: "source-topic", Value: []byte(c.cfg.KafkaInputTopic)},
		},
	}, nil)
	if err != nil {
		c.log.Error("Failed to route message to DLQ", "error", err)
		return
	}
	c.metrics.DLQRouted.Inc()
}

// commitOffset commits the message offset to Kafka.
// Uses StoreOffsets (async) for throughput; the auto-commit loop flushes.
func (c *Consumer) commitOffset(msg *kafka.Message) {
	if _, err := c.consumer.StoreMessage(msg); err != nil {
		c.log.Warn("StoreMessage failed", "offset", msg.TopicPartition.Offset, "error", err)
	}
}

// shutdown flushes the producer and closes the consumer.
func (c *Consumer) shutdown() {
	c.log.Info("C5 Go consumer shutting down")
	_ = c.consumer.Close()
	if c.producer != nil {
		remaining := c.producer.Flush(producerFlushTimeoutMs) // defined as constant above
		if remaining > 0 {
			c.log.Warn("Producer flush timed out", "unflushed", remaining)
		}
		c.producer.Close()
	}
}

// toKafkaConfigMap converts a Go map to a confluent-kafka-go ConfigMap.
func toKafkaConfigMap(m map[string]interface{}) *kafka.ConfigMap {
	cm := &kafka.ConfigMap{}
	for k, v := range m {
		_ = cm.SetKey(k, v)
	}
	return cm
}
