-- ==========================================
-- 单号库架构重构 SQL
-- ==========================================

-- 1. 创建单号库顶级表
CREATE TABLE waybill_stocks (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '单号库ID',
    airline_name VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '航司名称（如china_southern_air）',
    total_authorized_count INT COMMENT '核定单号总数',
    created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) NOT NULL COMMENT '创建时间（中国时间UTC+8）',
    updated_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) NOT NULL COMMENT '更新时间（中国时间UTC+8）',
    PRIMARY KEY (id),
    UNIQUE KEY idx_waybill_stocks_airline (airline_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单号库表';

-- 2. 给现有的领单批次表添加 stock_id 外键列
ALTER TABLE waybill_stock_batches ADD COLUMN stock_id BIGINT COMMENT '关联单号库ID' AFTER id;

-- 3. 数据迁移：将批次中已有的航司数据聚合成单号库记录（处理现有测试数据）
INSERT IGNORE INTO waybill_stocks (airline_name, total_authorized_count, created_at, updated_at)
SELECT airline_name, MAX(total_authorized_count), NOW(), NOW()
FROM waybill_stock_batches
GROUP BY airline_name;

-- 回填 stock_id
UPDATE waybill_stock_batches b
JOIN waybill_stocks s ON b.airline_name = s.airline_name
SET b.stock_id = s.id;

-- 4. 加上外键约束以及非空限制
-- 注意：如果现存有未匹配到的脏数据，这里加 NOT NULL 可能会报错，建议清理后执行
ALTER TABLE waybill_stock_batches MODIFY COLUMN stock_id BIGINT NOT NULL COMMENT '关联单号库ID';
ALTER TABLE waybill_stock_batches ADD CONSTRAINT fk_waybill_stock_batches_stock_id FOREIGN KEY (stock_id) REFERENCES waybill_stocks (id) ON DELETE CASCADE;

-- 5. 移除原批次表中已上升到单号库层级的冗余字段
ALTER TABLE waybill_stock_batches DROP COLUMN airline_name;
ALTER TABLE waybill_stock_batches DROP COLUMN total_authorized_count;
