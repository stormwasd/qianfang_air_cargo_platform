-- 费用登记台新增提交状态；历史数据均视为已提交（1）。
ALTER TABLE `cost_consignments`
ADD COLUMN `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '提交状态：0=未提交，1=已提交' AFTER `remark`,
ADD INDEX `idx_status` (`status`);
