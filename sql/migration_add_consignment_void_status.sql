-- 已执行过两台 status 字段迁移的存量数据库执行本脚本。
-- tinyint 字段本身已支持数值 2，本迁移统一更新字段注释以明确作废状态。
ALTER TABLE `consignment_infos`
MODIFY COLUMN `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '单据状态：0=未提交，1=已提交，2=作废';

ALTER TABLE `cost_consignments`
MODIFY COLUMN `status` tinyint(1) NOT NULL DEFAULT 1 COMMENT '单据状态：0=未提交，1=已提交，2=作废';
