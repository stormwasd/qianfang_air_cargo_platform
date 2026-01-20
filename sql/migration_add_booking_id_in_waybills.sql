-- 为 waybills 表添加 booking_id 字段（关联订舱ID）
ALTER TABLE waybills 
ADD COLUMN booking_id BIGINT NULL COMMENT '关联的订舱ID（可选，用于从订舱回显数据创建运单时建立关联）' AFTER id;

-- 为 booking_id 字段添加索引（提高查询性能）
CREATE INDEX idx_waybills_booking_id ON waybills(booking_id);