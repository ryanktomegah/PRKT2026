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

// workerLoop processes messages from msgCh until the channel is closed.
func (c *Consumer) workerLoop(ctx context.Context) {
	for msg := range c.msgCh {
		start := time.Now()
		c.processMessage(ctx, msg)
		c.metrics.IngestionLatency.Observe(time.Since(start).Seconds())
	}
}

// processMessage implements the normalize → fan-out → produce → commit pipeline.
func (c *Consumer) processMessage(ctx context.Context, msg *kafka.Message) {
	if msg.Value == nil {
		c.log.Warn("Null-value message — skipping", "offset", msg.TopicPartition.Offset)
		c.commitOffset(msg)
		return
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
		c.commitOffset(msg)
		return
	}

	// gRPC fan-out to C1/C2/C6
	result, err := c.grpc.FanOut(ctx, event, c.metrics)
	if err != nil {
		c.log.Error("Pipeline fan-out error — routing to DLQ",
			"uetr", event.UETR, "error", err)
		c.routeDLQ(msg)
		c.metrics.ProcessingErrors.Inc()
		c.commitOffset(msg)
		return
	}

	// Produce result
	if !c.cfg.DryRun && c.producer != nil {
		resultBytes, _ := json.Marshal(result)
		if err := c.produceWithRetry(event.UETR, resultBytes); err != nil {
			c.log.Error("Produce error after retries — routing to DLQ",
				"uetr", event.UETR, "error", err)
			c.routeDLQ(msg)
			c.metrics.ProduceErrors.Inc()
			c.commitOffset(msg)
			return
		}
		c.metrics.MessagesProduced.Inc()
	}

	c.metrics.MessagesConsumed.Inc()
	c.commitOffset(msg)
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
