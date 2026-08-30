-- 新增费用登记台应收款项运费计算方式字段
ALTER TABLE `cost_registrations`
    ADD COLUMN `freight_method` varchar(50) DEFAULT NULL COMMENT '运费计算方式' AFTER `unit_price`;

ALTER TABLE `cost_consignments`
    ADD COLUMN `freight_method` varchar(50) DEFAULT NULL COMMENT '运费计算方式' AFTER `unit_price`;
