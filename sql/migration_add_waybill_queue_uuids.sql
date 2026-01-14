-- 为waybills表添加队列相关字段
-- 执行时间：2026-01-14

ALTER TABLE `waybills` 
ADD COLUMN `rpa_queue_uuids` TEXT NULL COMMENT 'RPA队列UUIDs（JSON格式，存储4个队列的UUID和ID信息）' AFTER `rpa_work_uuid`;

