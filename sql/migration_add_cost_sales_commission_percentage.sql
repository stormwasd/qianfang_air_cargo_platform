-- 费用登记台销售提成新增“提成百分比”字段。
-- 存量数据库执行一次；全新数据库请直接使用 migration_create_cost_service_consignments.sql。

ALTER TABLE `cost_registrations`
    ADD COLUMN `commission_percentage` decimal(5,2) DEFAULT NULL COMMENT '提成百分比'
    AFTER `salesperson`;

ALTER TABLE `cost_consignments`
    ADD COLUMN `commission_percentage` decimal(5,2) DEFAULT NULL COMMENT '提成百分比'
    AFTER `salesperson`;
