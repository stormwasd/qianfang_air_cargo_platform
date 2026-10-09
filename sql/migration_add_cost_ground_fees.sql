-- 费用登记台地面操作新增 TC费、提货费；原 pay_ground_freight 列及数据保持不变。
ALTER TABLE `cost_registrations`
ADD COLUMN `pay_ground_tc_fee` decimal(10,2) DEFAULT NULL COMMENT '地面操作-TC费' AFTER `pay_ground_freight`,
ADD COLUMN `pay_ground_pickup_fee` decimal(10,2) DEFAULT NULL COMMENT '地面操作-提货费' AFTER `pay_ground_tc_fee`;

ALTER TABLE `cost_consignments`
ADD COLUMN `pay_ground_tc_fee` decimal(10,2) DEFAULT NULL COMMENT '地面操作-TC费' AFTER `pay_ground_freight`,
ADD COLUMN `pay_ground_pickup_fee` decimal(10,2) DEFAULT NULL COMMENT '地面操作-提货费' AFTER `pay_ground_tc_fee`;
