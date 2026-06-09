-- =====================================================================
--  PWIN AI — Philippine Weather Intelligence Network
--  MySQL 8.x schema (XAMPP-compatible)
--
--  Import via phpMyAdmin (Import tab) or:
--      mysql -u root -p < database/schema.sql
--
--  The FastAPI app also auto-creates the CORE tables via SQLAlchemy on
--  first run. This file is the canonical, fully-normalised design and adds
--  the extended history/risk/RBAC tables described in the spec.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS pwin_ai
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE pwin_ai;

SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------
--  Geography
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regions (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  code        VARCHAR(16) NOT NULL UNIQUE,
  name        VARCHAR(128) NOT NULL,
  lat         DOUBLE NOT NULL,
  lon         DOUBLE NOT NULL,
  INDEX ix_regions_name (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS provinces (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(128) NOT NULL UNIQUE,
  region_id   INT NOT NULL,
  capital     VARCHAR(128) DEFAULT '',
  lat         DOUBLE NOT NULL,
  lon         DOUBLE NOT NULL,
  CONSTRAINT fk_prov_region FOREIGN KEY (region_id) REFERENCES regions(id),
  INDEX ix_prov_region (region_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS cities (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(128) NOT NULL,
  province_id INT NOT NULL,
  lat         DOUBLE NOT NULL,
  lon         DOUBLE NOT NULL,
  CONSTRAINT fk_city_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_city_prov (province_id),
  INDEX ix_city_name (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS municipalities (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(128) NOT NULL,
  province_id INT NOT NULL,
  is_city     TINYINT(1) DEFAULT 0,
  lat         DOUBLE, lon DOUBLE,
  CONSTRAINT fk_mun_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_mun_prov (province_id),
  INDEX ix_mun_name (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS barangays (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  name            VARCHAR(128) NOT NULL,
  municipality_id INT NOT NULL,
  lat             DOUBLE, lon DOUBLE,
  CONSTRAINT fk_brgy_mun FOREIGN KEY (municipality_id) REFERENCES municipalities(id),
  INDEX ix_brgy_mun (municipality_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS weather_stations (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(128) NOT NULL,
  province_id INT NOT NULL,
  source      VARCHAR(64) DEFAULT 'open-meteo',
  lat DOUBLE, lon DOUBLE,
  CONSTRAINT fk_station_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_station_prov (province_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
--  Live + historical observations
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_readings (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  province_id     INT NOT NULL,
  observed_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  source          VARCHAR(64) DEFAULT 'open-meteo',
  temperature_c   DOUBLE, feels_like_c DOUBLE, humidity_pct DOUBLE,
  wind_speed_kmh  DOUBLE, wind_dir_deg DOUBLE, wind_gust_kmh DOUBLE,
  pressure_hpa    DOUBLE, visibility_km DOUBLE, uv_index DOUBLE,
  cloud_cover_pct DOUBLE, precip_mm DOUBLE, precip_prob_pct DOUBLE,
  condition_code  INT, condition_text VARCHAR(128),
  is_raining      TINYINT(1) DEFAULT 0,
  CONSTRAINT fk_read_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_reading_province_time (province_id, observed_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS weather_forecasts (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  province_id   INT NOT NULL,
  generated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  kind          VARCHAR(16) DEFAULT 'daily',
  horizon_days  INT DEFAULT 7,
  payload       JSON,
  CONSTRAINT fk_fc_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_fc_prov_time (province_id, generated_at)
) ENGINE=InnoDB;

-- Specialised history tables (normalised per-metric)
CREATE TABLE IF NOT EXISTS rainfall_records (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, province_id INT NOT NULL,
  recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  precip_mm DOUBLE, intensity VARCHAR(32),
  CONSTRAINT fk_rain_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_rain_prov_time (province_id, recorded_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS temperature_records (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, province_id INT NOT NULL,
  recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  temperature_c DOUBLE, feels_like_c DOUBLE,
  CONSTRAINT fk_temp_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_temp_prov_time (province_id, recorded_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS humidity_records (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, province_id INT NOT NULL,
  recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, humidity_pct DOUBLE,
  CONSTRAINT fk_hum_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_hum_prov_time (province_id, recorded_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS wind_records (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, province_id INT NOT NULL,
  recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  wind_speed_kmh DOUBLE, wind_dir_deg DOUBLE, wind_gust_kmh DOUBLE,
  CONSTRAINT fk_wind_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_wind_prov_time (province_id, recorded_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pressure_records (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, province_id INT NOT NULL,
  recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, pressure_hpa DOUBLE,
  CONSTRAINT fk_pres_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_pres_prov_time (province_id, recorded_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
--  Events, alerts and risk
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_events (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  province_id   INT NOT NULL,
  event_type    VARCHAR(64) NOT NULL,
  severity      VARCHAR(32) NOT NULL,
  cause         VARCHAR(128) DEFAULT '',
  rain_intensity VARCHAR(32) DEFAULT 'none',
  risk_level    VARCHAR(32) DEFAULT 'low',
  risk_score    DOUBLE DEFAULT 0,
  confidence    DOUBLE DEFAULT 0.6,
  started_at    DATETIME NULL,
  expected_end  DATETIME NULL,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  summary       TEXT,
  active        TINYINT(1) DEFAULT 1,
  CONSTRAINT fk_event_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_event_prov (province_id),
  INDEX ix_event_active (active),
  INDEX ix_event_sev (severity)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS weather_alerts (
  id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
  title              VARCHAR(160) NOT NULL,
  category           VARCHAR(64) NOT NULL,
  severity           VARCHAR(32) NOT NULL,
  province_id        INT NULL,
  areas              JSON,
  reason             TEXT,
  recommended_action TEXT,
  issued_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at         DATETIME NULL,
  source             VARCHAR(64) DEFAULT 'PWIN AI',
  active             TINYINT(1) DEFAULT 1,
  CONSTRAINT fk_alert_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_alert_active (active),
  INDEX ix_alert_sev (severity),
  INDEX ix_alert_cat (category)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS storm_tracks (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  name         VARCHAR(96) NOT NULL,
  category     VARCHAR(48),
  recorded_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  lat DOUBLE, lon DOUBLE,
  max_wind_kmh DOUBLE, gust_kmh DOUBLE, pressure_hpa DOUBLE,
  movement     VARCHAR(64),
  INDEX ix_storm_name_time (name, recorded_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS flood_risk_records (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, province_id INT NOT NULL,
  assessed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  risk_level VARCHAR(32), risk_score DOUBLE, basis TEXT,
  CONSTRAINT fk_flood_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_flood_prov_time (province_id, assessed_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS landslide_risk_records (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, province_id INT NOT NULL,
  assessed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  risk_level VARCHAR(32), risk_score DOUBLE, basis TEXT,
  CONSTRAINT fk_land_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_land_prov_time (province_id, assessed_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
--  AI outputs
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_reports (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  scope        VARCHAR(32) DEFAULT 'national',
  scope_ref    VARCHAR(128) DEFAULT 'PH',
  generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  engine       VARCHAR(32) DEFAULT 'rule-engine',
  headline     VARCHAR(255),
  body         TEXT,
  INDEX ix_aireport_time (generated_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ai_event_explanations (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  province_id  INT NOT NULL,
  generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  engine       VARCHAR(32) DEFAULT 'rule-engine',
  what         TEXT, `where` TEXT,
  when_started VARCHAR(255), when_end VARCHAR(255), why TEXT,
  severity     VARCHAR(32) DEFAULT 'info', confidence DOUBLE DEFAULT 0.6,
  precautions  JSON,
  CONSTRAINT fk_aiexp_prov FOREIGN KEY (province_id) REFERENCES provinces(id),
  INDEX ix_aiexp_prov (province_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
--  RBAC + audit
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(64) NOT NULL UNIQUE,
  description VARCHAR(255) DEFAULT ''
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS permissions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  description VARCHAR(255) DEFAULT ''
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS role_permissions (
  role_id INT NOT NULL, permission_id INT NOT NULL,
  PRIMARY KEY (role_id, permission_id),
  CONSTRAINT fk_rp_role FOREIGN KEY (role_id) REFERENCES roles(id),
  CONSTRAINT fk_rp_perm FOREIGN KEY (permission_id) REFERENCES permissions(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS users (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  username        VARCHAR(64) NOT NULL UNIQUE,
  email           VARCHAR(128) NOT NULL UNIQUE,
  hashed_password VARCHAR(255) NOT NULL,
  role_id         INT NULL,
  is_active       TINYINT(1) DEFAULT 1,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_user_role FOREIGN KEY (role_id) REFERENCES roles(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS activity_logs (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id    INT NULL,
  action     VARCHAR(128) NOT NULL,
  detail     TEXT,
  ip_address VARCHAR(64) DEFAULT '',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_log_user FOREIGN KEY (user_id) REFERENCES users(id),
  INDEX ix_log_time (created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS system_logs (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  level      VARCHAR(16) NOT NULL,
  component  VARCHAR(64),
  message    TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_syslog_time (created_at)
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
--  Seed roles + permissions
-- ---------------------------------------------------------------------
INSERT IGNORE INTO roles (name, description) VALUES
  ('admin', 'Full administrative access'),
  ('operator', 'Operations: trigger refresh, manage alerts'),
  ('viewer', 'Read-only access');

INSERT IGNORE INTO permissions (code, description) VALUES
  ('weather.read', 'Read weather data'),
  ('weather.refresh', 'Trigger data refresh'),
  ('alerts.manage', 'Create/expire alerts'),
  ('admin.users', 'Manage users and roles');
