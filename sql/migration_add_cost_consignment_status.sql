-- 费用登记台新增单据状态；历史数据均视为已提交（1）。
ALTER TABLE `cost_consignments`
ADD COLUMN `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '单据状态：0=未提交，1=已提交，2=作废' AFTER `remark`,
ADD INDEX `idx_status` (`status`);
