-- 为bookings表添加队列相关字段
-- 执行时间：2026-01-14

ALTER TABLE `bookings` 
ADD COLUMN `rpa_queue_uuid` VARCHAR(100) NULL COMMENT 'RPA队列UUID（动态创建，用于获取运单号）' AFTER `rpa_work_uuid`,
ADD COLUMN `rpa_queue_id` VARCHAR(100) NULL COMMENT 'RPA队列ID（动态创建，用于删除队列）' AFTER `rpa_queue_uuid`,
ADD INDEX `idx_rpa_queue_uuid` (`rpa_queue_uuid`);

