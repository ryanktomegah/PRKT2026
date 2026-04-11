// config_test.go — Unit tests for C5 Go consumer configuration loading.
package main

import (
	"os"
	"testing"
)

func TestLoadConfigDefaults(t *testing.T) {
	// Ensure no stray env vars from other tests
	clearEnv()
	// B6-05: default protocol is SSL, but unit tests have no certs; use PLAINTEXT.
	t.Setenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig failed with defaults: %v", err)
	}

	assertEqual(t, "KafkaBootstrapServers", "kafka:9092", cfg.KafkaBootstrapServers)
	assertEqual(t, "KafkaGroupID", "lip-c5-go-worker", cfg.KafkaGroupID)
	assertEqual(t, "KafkaInputTopic", "lip.payment.events", cfg.KafkaInputTopic)
	assertEqual(t, "KafkaOutputTopic", "lip.failure.predictions", cfg.KafkaOutputTopic)
	assertEqual(t, "KafkaDLQTopic", "lip.dead.letter", cfg.KafkaDLQTopic)
	assertEqual(t, "MetricsAddr", ":9090", cfg.MetricsAddr)
	assertEqual(t, "GRPCC1Addr", "c1-service:50051", cfg.GRPCC1Addr)

	if cfg.NumWorkers != 8 {
		t.Errorf("NumWorkers: expected 8, got %d", cfg.NumWorkers)
	}
	if cfg.DryRun {
		t.Error("DryRun should be false by default")
	}
}

func TestLoadConfigEnvOverride(t *testing.T) {
	clearEnv()
	// B6-05: default protocol is SSL; override to PLAINTEXT for this non-SSL test.
	t.Setenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
	t.Setenv("KAFKA_BOOTSTRAP_SERVERS", "broker1:9092,broker2:9092")
	t.Setenv("KAFKA_GROUP_ID", "test-group")
	t.Setenv("NUM_WORKERS", "4")
	t.Setenv("DRY_RUN", "true")

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}

	assertEqual(t, "bootstrap", "broker1:9092,broker2:9092", cfg.KafkaBootstrapServers)
	assertEqual(t, "group", "test-group", cfg.KafkaGroupID)
	if cfg.NumWorkers != 4 {
		t.Errorf("NumWorkers: expected 4, got %d", cfg.NumWorkers)
	}
	if !cfg.DryRun {
		t.Error("DryRun should be true")
	}
}

func TestLoadConfigInvalidNumWorkers(t *testing.T) {
	clearEnv()
	t.Setenv("NUM_WORKERS", "0")
	_, err := LoadConfig()
	if err == nil {
		t.Error("expected error for NUM_WORKERS=0")
	}
}

func TestKafkaConsumerConfigMap(t *testing.T) {
	clearEnv()
	t.Setenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
	cfg, _ := LoadConfig()
	m := cfg.KafkaConsumerConfigMap()

	if m["enable.auto.commit"] != false {
		t.Error("enable.auto.commit should be false for exactly-once semantics")
	}
	if m["isolation.level"] != "read_committed" {
		t.Error("isolation.level should be read_committed")
	}
}

func TestKafkaProducerConfigMap(t *testing.T) {
	clearEnv()
	t.Setenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
	cfg, _ := LoadConfig()
	m := cfg.KafkaProducerConfigMap()

	if m["enable.idempotence"] != true {
		t.Error("enable.idempotence should be true")
	}
	if m["acks"] != "all" {
		t.Error("acks should be all")
	}
}

func TestSSLConfig(t *testing.T) {
	clearEnv()
	t.Setenv("KAFKA_SECURITY_PROTOCOL", "SSL")
	t.Setenv("KAFKA_SSL_CA_LOCATION", "/etc/ssl/ca.pem")
	t.Setenv("KAFKA_SSL_CERT_LOCATION", "/etc/ssl/cert.pem")
	t.Setenv("KAFKA_SSL_KEY_LOCATION", "/etc/ssl/key.pem")

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
	m := cfg.KafkaConsumerConfigMap()

	if m["security.protocol"] != "SSL" {
		t.Errorf("security.protocol: expected SSL, got %v", m["security.protocol"])
	}
	if m["ssl.ca.location"] != "/etc/ssl/ca.pem" {
		t.Errorf("ssl.ca.location: got %v", m["ssl.ca.location"])
	}
}

func clearEnv() {
	keys := []string{
		"KAFKA_BOOTSTRAP_SERVERS", "KAFKA_GROUP_ID",
		"KAFKA_INPUT_TOPIC", "KAFKA_OUTPUT_TOPIC", "KAFKA_DLQ_TOPIC",
		"KAFKA_SSL_CA_LOCATION", "KAFKA_SSL_CERT_LOCATION", "KAFKA_SSL_KEY_LOCATION",
		"KAFKA_SECURITY_PROTOCOL", "SCHEMA_REGISTRY_URL",
		"REDIS_ADDR", "REDIS_PASSWORD", "REDIS_TLS_ENABLE",
		"GRPC_C1_ADDR", "GRPC_C2_ADDR", "GRPC_C6_ADDR",
		"NUM_WORKERS", "DRY_RUN", "LOG_LEVEL", "METRICS_ADDR",
	}
	for _, k := range keys {
		os.Unsetenv(k)
	}
}
