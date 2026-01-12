-- ============================================
-- waybills表字段迁移脚本
-- 用于支持运单作废功能
-- ============================================

-- 添加waybill_void_status字段
-- 用于存储运单作废状态（数据字典值：0=未作废，1=作废中，2=作废失败，3=作废成功）
ALTER TABLE `waybills` 
ADD COLUMN `waybill_void_status` VARCHAR(20) NULL DEFAULT '0' COMMENT '运单作废状态（数据字典值：0=未作废，1=作废中，2=作废失败，3=作废成功）' AFTER `document_print_status`;

-- 为waybill_void_status字段添加索引，提高查询性能
CREATE INDEX `idx_waybills_waybill_void_status` ON `waybills` (`waybill_void_status`);

