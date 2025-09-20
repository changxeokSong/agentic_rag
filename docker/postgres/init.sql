-- Initial schema for synergy project
-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- Files table for binary contents and metadata
CREATE TABLE IF NOT EXISTS files (
  id SERIAL PRIMARY KEY,
  filename TEXT NOT NULL UNIQUE,
  upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  length BIGINT NOT NULL,
  metadata JSONB,
  content BYTEA
);

-- Chunks table for RAG
CREATE TABLE IF NOT EXISTS chunks (
  id SERIAL PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content TEXT,
  embedding vector(1024),
  metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

-- Water table for monitoring service
CREATE TABLE IF NOT EXISTS water (
  measured_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  gagok_water_level DOUBLE PRECISION,
  gagok_pump_a DOUBLE PRECISION,
  gagok_pump_b DOUBLE PRECISION,
  haeryong_water_level DOUBLE PRECISION,
  haeryong_pump_a DOUBLE PRECISION,
  haeryong_pump_b DOUBLE PRECISION,
  sangsa_water_level DOUBLE PRECISION,
  sangsa_pump_a DOUBLE PRECISION,
  sangsa_pump_b DOUBLE PRECISION,
  sangsa_pump_c DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_water_measured_at ON water(measured_at);


