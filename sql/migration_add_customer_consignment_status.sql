-- 客服接单台新增提交状态；历史数据均视为已提交（1）。
ALTER TABLE `consignment_infos`
ADD COLUMN `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '提交状态：0=未提交，1=已提交' AFTER `remark`,
ADD INDEX `idx_status` (`status`);
