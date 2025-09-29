\set ON_ERROR_STOP on
-- ================================
-- Synergy Project: Schema & Seed
-- ================================
SET client_encoding TO 'UTF8';
SET datestyle TO 'ISO, YMD';
SET timezone TO 'UTC';

CREATE EXTENSION IF NOT EXISTS vector;

-- ---- schema ----
CREATE TABLE IF NOT EXISTS files (
  id SERIAL PRIMARY KEY,
  filename TEXT NOT NULL UNIQUE,
  upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  length BIGINT NOT NULL,
  metadata JSONB,
  content BYTEA
);

CREATE TABLE IF NOT EXISTS chunks (
  id SERIAL PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content TEXT,
  embedding vector(1024),
  metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
  ON chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

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
CREATE UNIQUE INDEX IF NOT EXISTS ux_water_measured_at ON water(measured_at);

-- ---- stable staging (영구 스테이징; 끝에 DROP) ----
DROP TABLE IF EXISTS water_stage;
CREATE TABLE water_stage (
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

-- CSV -> staging (파일은 같은 폴더가 /docker-entrypoint-initdb.d 로 마운트됨)
COPY water_stage (
  measured_at,
  gagok_water_level,
  gagok_pump_a,
  gagok_pump_b,
  haeryong_water_level,
  haeryong_pump_a,
  haeryong_pump_b,
  sangsa_water_level,
  sangsa_pump_a,
  sangsa_pump_b,
  sangsa_pump_c
) FROM '/docker-entrypoint-initdb.d/water.csv'
  WITH (
    FORMAT csv,
    HEADER true,
    NULL 'NULL',                                -- "NULL" 문자열을 실제 NULL로 처리
    FORCE_NULL (
      gagok_water_level,
      gagok_pump_a,
      gagok_pump_b,
      haeryong_water_level,
      haeryong_pump_a,
      haeryong_pump_b,
      sangsa_water_level,
      sangsa_pump_a,
      sangsa_pump_b,
      sangsa_pump_c
    )                                            -- 빈 칸(,)도 NULL로 강제
  );

-- staging -> 본 테이블 (중복 무시)
INSERT INTO water AS w (
  measured_at,
  gagok_water_level,
  gagok_pump_a,
  gagok_pump_b,
  haeryong_water_level,
  haeryong_pump_a,
  haeryong_pump_b,
  sangsa_water_level,
  sangsa_pump_a,
  sangsa_pump_b,
  sangsa_pump_c
)
SELECT
  s.measured_at,
  s.gagok_water_level,
  s.gagok_pump_a,
  s.gagok_pump_b,
  s.haeryong_water_level,
  s.haeryong_pump_a,
  s.haeryong_pump_b,
  s.sangsa_water_level,
  s.sangsa_pump_a,
  s.sangsa_pump_b,
  s.sangsa_pump_c
FROM water_stage s
ON CONFLICT (measured_at) DO NOTHING;

-- 정리
DROP TABLE water_stage;

-- 간단 검증 로그
DO $$
DECLARE c bigint; e timestamp; l timestamp;
BEGIN
  SELECT COUNT(*), MIN(measured_at), MAX(measured_at)
  INTO c, e, l FROM water;
  RAISE LOG 'water rows=% count, range=[% .. %]', c, e, l;
END$$;
