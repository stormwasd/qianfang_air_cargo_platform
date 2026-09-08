-- 费用登记台应收款项新增燃油费字段。
ALTER TABLE `cost_registrations`
ADD COLUMN `receivable_fuel_fee` decimal(10,2) DEFAULT NULL COMMENT '燃油费' AFTER `receivable_freight`;

ALTER TABLE `cost_consignments`
ADD COLUMN `receivable_fuel_fee` decimal(10,2) DEFAULT NULL COMMENT '燃油费' AFTER `receivable_freight`;
