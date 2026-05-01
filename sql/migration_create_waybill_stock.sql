-- 单号库功能建表SQL
-- 包含两张表：领单批次表和单号详情表

-- 领单批次表
CREATE TABLE IF NOT EXISTS waybill_stock_batches (
    id BIGINT PRIMARY KEY COMMENT '领单批次ID（雪花算法）',
    claim_date DATE NOT NULL COMMENT '领单日期',
    first_number VARCHAR(50) NOT NULL COMMENT '首单号（数字后缀部分）',
    last_number VARCHAR(50) NOT NULL COMMENT '尾单号（数字后缀部分）',
    claim_quantity INT NOT NULL COMMENT '领单数量',
    airline_name VARCHAR(100) NOT NULL COMMENT '航司名称（如china_southern_air）',
    number_prefix VARCHAR(20) NOT NULL COMMENT '单号前缀（如784-）',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间（中国时间UTC+8）',
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间（中国时间UTC+8）',
    INDEX idx_airline_name (airline_name),
    INDEX idx_claim_date (claim_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='领单批次表';

-- 单号详情表
CREATE TABLE IF NOT EXISTS waybill_stock_items (
    id BIGINT PRIMARY KEY COMMENT '单号详情ID（雪花算法）',
    batch_id BIGINT NOT NULL COMMENT '关联领单批次ID',
    claim_date DATE NOT NULL COMMENT '领单日期',
    number_prefix VARCHAR(20) NOT NULL COMMENT '单号前缀（如784-）',
    number_suffix VARCHAR(50) NOT NULL COMMENT '单号后缀（数字部分）',
    full_number VARCHAR(100) NOT NULL COMMENT '完整单号（前缀+后缀）',
    usage_status VARCHAR(2) NOT NULL DEFAULT '0' COMMENT '使用状态（0=未使用，1=已使用，2=异常，3=失效）',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间（中国时间UTC+8）',
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间（中国时间UTC+8）',
    INDEX idx_batch_id (batch_id),
    INDEX idx_full_number (full_number),
    INDEX idx_usage_status (usage_status),
    CONSTRAINT fk_waybill_stock_items_batch_id FOREIGN KEY (batch_id) REFERENCES waybill_stock_batches(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单号详情表';
