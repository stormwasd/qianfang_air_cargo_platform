-- 费用登记台折让信息新增费率字段。
ALTER TABLE `cost_registrations`
ADD COLUMN `discount_rate` decimal(10,2) DEFAULT NULL COMMENT '折让费率' AFTER `discount_person`;

ALTER TABLE `cost_consignments`
ADD COLUMN `discount_rate` decimal(10,2) DEFAULT NULL COMMENT '折让费率' AFTER `discount_person`;
