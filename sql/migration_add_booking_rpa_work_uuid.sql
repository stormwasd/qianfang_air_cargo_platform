-- ============================================
-- bookings表字段迁移脚本
-- 用于支持南航订舱RPA功能
-- ============================================

-- 添加rpa_work_uuid字段
-- 用于存储RPA任务返回的workUuid，用于查询RPA执行状态
ALTER TABLE `bookings` 
ADD COLUMN `rpa_work_uuid` VARCHAR(100) NULL COMMENT 'RPA任务workUuid（用于查询RPA执行状态）' AFTER `master_airwaybill_number`;

-- 为rpa_work_uuid字段添加索引，提高查询性能
CREATE INDEX `idx_bookings_rpa_work_uuid` ON `bookings` (`rpa_work_uuid`);

