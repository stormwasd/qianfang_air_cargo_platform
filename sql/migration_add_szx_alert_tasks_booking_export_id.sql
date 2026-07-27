-- ================================================================
-- 数据库迁移脚本：深航企微预警任务表引入 booking_export_id 物理主键字段
-- 日期: 2026-07-27
-- 说明: 为深航装机预警与过机预警任务表增加 booking_export_id 字段并创建唯一索引
-- ================================================================

-- 1. 深航装机状态预警任务表 (shenzhen_air_loading_alert_tasks)
ALTER TABLE shenzhen_air_loading_alert_tasks 
ADD COLUMN booking_export_id BIGINT COMMENT '关联 shenzhen_air_booking_exports.id';

ALTER TABLE shenzhen_air_loading_alert_tasks 
ADD UNIQUE INDEX uk_szx_loading_booking_export_id (booking_export_id);

-- 删除旧的组合唯一索引（防止运单号前缀格式不一致触发唯一索引报错）
ALTER TABLE shenzhen_air_loading_alert_tasks 
DROP INDEX ix_szx_loading_alert_waybill_date;

-- 为 waybill_number 和 flight_date 保留普通检索索引
ALTER TABLE shenzhen_air_loading_alert_tasks 
ADD INDEX idx_szx_loading_waybill_date (waybill_number, flight_date);


-- 2. 深航出港跟踪/过机预警任务表 (shenzhen_air_departure_alert_tasks)
ALTER TABLE shenzhen_air_departure_alert_tasks 
ADD COLUMN booking_export_id BIGINT COMMENT '关联 shenzhen_air_booking_exports.id';

ALTER TABLE shenzhen_air_departure_alert_tasks 
ADD UNIQUE INDEX uk_szx_departure_booking_export_id (booking_export_id);

-- 删除旧的组合唯一索引（防止运单号前缀格式不一致触发唯一索引报错）
ALTER TABLE shenzhen_air_departure_alert_tasks 
DROP INDEX ix_szx_departure_alert_waybill_date;

-- 为 waybill_number 和 flight_date 保留普通检索索引
ALTER TABLE shenzhen_air_departure_alert_tasks 
ADD INDEX idx_szx_departure_waybill_date (waybill_number, flight_date);
