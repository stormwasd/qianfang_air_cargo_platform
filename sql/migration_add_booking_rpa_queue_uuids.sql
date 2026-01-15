-- 为bookings表添加rpa_queue_uuids字段
-- 执行时间：2026-01-15

ALTER TABLE `bookings` 
ADD COLUMN `rpa_queue_uuids` TEXT NULL COMMENT 'RPA队列UUIDs和IDs（JSON格式，用于直接开单时存储多个队列信息）' AFTER `rpa_queue_id`;

