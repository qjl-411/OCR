-- 票序 智能发票系统 · 账号库初始化
-- 仅存放登录账号与邮箱验证码；发票台账等业务数据仍保存在本机 SQLite。

CREATE DATABASE IF NOT EXISTS piao_invoice
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE piao_invoice;

CREATE TABLE IF NOT EXISTS users (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email         VARCHAR(190)    NOT NULL,
  name          VARCHAR(64)     NOT NULL,
  company       VARCHAR(128)    NOT NULL DEFAULT '',
  password_hash VARCHAR(255)    NOT NULL,
  is_active     TINYINT         NOT NULL DEFAULT 1,
  created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_login_at DATETIME        NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_email (email),
  KEY idx_users_company (company)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 邮箱验证码：只保存验证码哈希，不落库明文；过期或用完即失效。
CREATE TABLE IF NOT EXISTS email_codes (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email       VARCHAR(190)    NOT NULL,
  code_hash   VARCHAR(255)    NOT NULL,
  purpose     VARCHAR(16)     NOT NULL DEFAULT 'register',
  attempts    INT             NOT NULL DEFAULT 0,
  expires_at  DATETIME        NOT NULL,
  consumed_at DATETIME        NULL,
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_codes_email (email, purpose),
  KEY idx_codes_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
