-- ============================================
-- settlements表字段迁移脚本
-- 用于支持运单作废状态同步到结算单
-- ============================================

-- 添加waybill_void_status字段
-- 用于存储运单作废状态（从waybills表同步，数据字典值：0=未作废，1=作废中，2=作废失败，3=作废成功）
ALTER TABLE `settlements` 
ADD COLUMN `waybill_void_status` VARCHAR(20) NOT NULL DEFAULT '0' COMMENT '运单作废状态（数据字典值：0=未作废，1=作废中，2=作废失败，3=作废成功），从waybills表同步' AFTER `form_data`;

-- 为waybill_void_status字段添加索引，提高查询性能
CREATE INDEX `idx_settlements_waybill_void_status` ON `settlements` (`waybill_void_status`);

