// config.go — Environment-driven configuration for the C5 Go Kafka consumer.
//
// All settings are read from environment variables so the service integrates
// with the existing Python-managed configuration layer (feature flags and
// per-corridor overrides live in Python; hot-path config lives here).
package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config holds all runtime configuration for the Go consumer service.
type Config struct {
	// Kafka settings
	KafkaBootstrapServers string
	KafkaGroupID          string
	KafkaInputTopic       string
	KafkaOutputTopic      string
	KafkaDLQTopic         string
	KafkaSSLCALocation    string
	KafkaSSLCertLocation  string
	KafkaSSLKeyLocation   string
	KafkaSecurityProtocol string

	// Schema Registry
	SchemaRegistryURL      string
	SchemaRegistryUsername string
	SchemaRegistryPassword string

	// Redis
	RedisAddr     string
	RedisPassword string
	RedisTLSEnable bool
	RedisSocketTimeout time.Duration

	// gRPC upstream endpoints (C1, C2, C6)
	GRPCC1Addr string
	GRPCC2Addr string
	GRPCC6Addr string
	GRPCTimeout time.Duration

	// Worker settings
	DryRun         bool
	NumWorkers     int
	PollTimeoutMs  int
	DLQMaxRetries  int
	DLQBackoffBase time.Duration

	// Canonical constants (QUANT-governed; mirror lip/common/constants.py)
	FeeFloorBPS float64

	// Observability
	MetricsAddr    string // :9090
	LogLevel       string
}

// LoadConfig reads all settings from environment variables, applying
// production-safe defaults. Missing required variables return an error.
func LoadConfig() (*Config, error) {
	cfg := &Config{
		KafkaBootstrapServers: envOrDefault("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
		KafkaGroupID:          envOrDefault("KAFKA_GROUP_ID", "lip-c5-go-worker"),
		KafkaInputTopic:       envOrDefault("KAFKA_INPUT_TOPIC", "lip.payment.events"),
		KafkaOutputTopic:      envOrDefault("KAFKA_OUTPUT_TOPIC", "lip.failure.predictions"),
		KafkaDLQTopic:         envOrDefault("KAFKA_DLQ_TOPIC", "lip.dead.letter"),
		KafkaSSLCALocation:    os.Getenv("KAFKA_SSL_CA_LOCATION"),
		KafkaSSLCertLocation:  os.Getenv("KAFKA_SSL_CERT_LOCATION"),
		KafkaSSLKeyLocation:   os.Getenv("KAFKA_SSL_KEY_LOCATION"),
		KafkaSecurityProtocol: envOrDefault("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),

		SchemaRegistryURL:      envOrDefault("SCHEMA_REGISTRY_URL", ""),
		SchemaRegistryUsername: os.Getenv("SCHEMA_REGISTRY_USERNAME"),
		SchemaRegistryPassword: os.Getenv("SCHEMA_REGISTRY_PASSWORD"),

		RedisAddr:          envOrDefault("REDIS_ADDR", "redis:6379"),
		RedisPassword:      os.Getenv("REDIS_PASSWORD"),
		RedisTLSEnable:     envBool("REDIS_TLS_ENABLE", false),
		RedisSocketTimeout: envDuration("REDIS_SOCKET_TIMEOUT_MS", 94) * time.Millisecond,

		GRPCC1Addr:  envOrDefault("GRPC_C1_ADDR", "c1-service:50051"),
		GRPCC2Addr:  envOrDefault("GRPC_C2_ADDR", "c2-service:50052"),
		GRPCC6Addr:  envOrDefault("GRPC_C6_ADDR", "c6-service:50056"),
		GRPCTimeout: envDuration("GRPC_TIMEOUT_MS", 80) * time.Millisecond,

		DryRun:         envBool("DRY_RUN", false),
		NumWorkers:     envInt("NUM_WORKERS", 8),
		PollTimeoutMs:  envInt("POLL_TIMEOUT_MS", 1000),
		DLQMaxRetries:  envInt("DLQ_MAX_RETRIES", 3),
		DLQBackoffBase: envDuration("DLQ_BACKOFF_BASE_MS", 100) * time.Millisecond,

		FeeFloorBPS: envFloat("FEE_FLOOR_BPS", 300.0),

		MetricsAddr: envOrDefault("METRICS_ADDR", ":9090"),
		LogLevel:    envOrDefault("LOG_LEVEL", "info"),
	}

	if err := cfg.validate(); err != nil {
		return nil, fmt.Errorf("invalid config: %w", err)
	}
	return cfg, nil
}

func (c *Config) validate() error {
	if strings.TrimSpace(c.KafkaBootstrapServers) == "" {
		return fmt.Errorf("KAFKA_BOOTSTRAP_SERVERS must not be empty")
	}
	if c.NumWorkers < 1 || c.NumWorkers > 64 {
		return fmt.Errorf("NUM_WORKERS must be 1-64, got %d", c.NumWorkers)
	}
	return nil
}

// KafkaProducerConfigMap returns a librdkafka-compatible config map for the
// output producer. Mirrors the Python KafkaConfig.to_producer_config().
func (c *Config) KafkaProducerConfigMap() map[string]interface{} {
	m := map[string]interface{}{
		"bootstrap.servers":        c.KafkaBootstrapServers,
		"enable.idempotence":       true,
		"acks":                     "all",
		"retries":                  2147483647,
		"max.in.flight.requests.per.connection": 5,
		"compression.type":         "snappy",
		"linger.ms":                5,
		"batch.size":               65536,
	}
	c.applySSL(m)
	return m
}

// KafkaConsumerConfigMap returns a librdkafka-compatible config map for the
// input consumer. Mirrors KafkaConfig.to_consumer_config().
func (c *Config) KafkaConsumerConfigMap() map[string]interface{} {
	m := map[string]interface{}{
		"bootstrap.servers":        c.KafkaBootstrapServers,
		"group.id":                 c.KafkaGroupID,
		"auto.offset.reset":        "earliest",
		"enable.auto.commit":       false, // manual offset commit for exactly-once
		"isolation.level":          "read_committed",
		"fetch.min.bytes":          1,
		"fetch.wait.max.ms":        500,
		"max.poll.interval.ms":     300000,
		"session.timeout.ms":       30000,
		"heartbeat.interval.ms":    3000,
	}
	c.applySSL(m)
	return m
}

func (c *Config) applySSL(m map[string]interface{}) {
	if c.KafkaSecurityProtocol != "PLAINTEXT" {
		m["security.protocol"] = c.KafkaSecurityProtocol
	}
	if c.KafkaSSLCALocation != "" {
		m["ssl.ca.location"] = c.KafkaSSLCALocation
	}
	if c.KafkaSSLCertLocation != "" {
		m["ssl.certificate.location"] = c.KafkaSSLCertLocation
	}
	if c.KafkaSSLKeyLocation != "" {
		m["ssl.key.location"] = c.KafkaSSLKeyLocation
	}
}

// ── helpers ──────────────────────────────────────────────────────────────────

func envOrDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envBool(key string, def bool) bool {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	b, err := strconv.ParseBool(v)
	if err != nil {
		return def
	}
	return b
}

func envInt(key string, def int) int {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return def
	}
	return n
}

func envFloat(key string, def float64) float64 {
	v := os.Getenv(key)
	if v == "" {
		return def
	}
	f, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return def
	}
	return f
}

func envDuration(key string, defMs int64) time.Duration {
	v := os.Getenv(key)
	if v == "" {
		return time.Duration(defMs)
	}
	n, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return time.Duration(defMs)
	}
	return time.Duration(n)
}
