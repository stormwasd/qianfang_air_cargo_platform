-- 上线前执行一次；旧数据保持 NULL，不推断费率、不回算金额。
ALTER TABLE `consignment_registrations` ADD COLUMN `financial_data` JSON DEFAULT NULL COMMENT '客服应收应付录入信息';

ALTER TABLE `consignment_infos` ADD COLUMN `financial_data` JSON DEFAULT NULL COMMENT '客服应收应付录入信息';

ALTER TABLE `cost_registrations`
ADD COLUMN `receivable_buy_order_fee` decimal(10,2) DEFAULT NULL COMMENT 'receivables-买单费/单',
ADD COLUMN `receivable_document_fee` decimal(10,2) DEFAULT NULL COMMENT 'receivables-单证费/单',
ADD COLUMN `receivable_fuel_rate` decimal(10,2) DEFAULT NULL COMMENT 'receivables-燃油费率',
ADD COLUMN `receivable_fuel_weight_method` varchar(50) DEFAULT NULL COMMENT 'receivables-燃油费取重方式',
ADD COLUMN `receivable_tc_rate` decimal(10,2) DEFAULT NULL COMMENT 'receivables-TC费率',
ADD COLUMN `receivable_front_warehouse_rate` decimal(10,2) DEFAULT NULL COMMENT 'receivables-前置仓费率',
ADD COLUMN `receivable_remark` text DEFAULT NULL COMMENT 'receivables-应收备注',
ADD COLUMN `pay_intl_air_buy_order_fee` decimal(10,2) DEFAULT NULL COMMENT 'payables.intl_air-买单费/单',
ADD COLUMN `pay_intl_air_document_fee` decimal(10,2) DEFAULT NULL COMMENT 'payables.intl_air-单证费/单',
ADD COLUMN `pay_intl_air_fuel_rate` decimal(10,2) DEFAULT NULL COMMENT 'payables.intl_air-燃油费率',
ADD COLUMN `pay_intl_air_fuel_weight_method` varchar(50) DEFAULT NULL COMMENT 'payables.intl_air-燃油费取重方式',
ADD COLUMN `pay_intl_air_tc_rate` decimal(10,2) DEFAULT NULL COMMENT 'payables.intl_air-TC费率',
ADD COLUMN `pay_intl_air_front_warehouse_rate` decimal(10,2) DEFAULT NULL COMMENT 'payables.intl_air-前置仓费率',
ADD COLUMN `pay_customs_buy_order_fee` decimal(10,2) DEFAULT NULL COMMENT 'payables.customs-买单费/单',
ADD COLUMN `pay_customs_document_fee` decimal(10,2) DEFAULT NULL COMMENT 'payables.customs-单证费/单',
ADD COLUMN `pay_ground_tc_rate` decimal(10,2) DEFAULT NULL COMMENT 'payables.ground-TC费率',
ADD COLUMN `pay_trucking_flight_doc_no` varchar(100) DEFAULT NULL COMMENT 'payables.trucking-主单号',
ADD COLUMN `pay_trucking_origin_city` varchar(100) DEFAULT NULL COMMENT 'payables.trucking-始发城市',
ADD COLUMN `pay_trucking_destination_city` varchar(100) DEFAULT NULL COMMENT 'payables.trucking-目的城市',
ADD COLUMN `pay_dom_air_volume` decimal(10,3) DEFAULT NULL COMMENT 'payables.dom_air-体积';

ALTER TABLE `cost_consignments`
ADD COLUMN `receivable_buy_order_fee` decimal(10,2) DEFAULT NULL COMMENT 'receivables-买单费/单',
ADD COLUMN `receivable_document_fee` decimal(10,2) DEFAULT NULL COMMENT 'receivables-单证费/单',
ADD COLUMN `receivable_fuel_rate` decimal(10,2) DEFAULT NULL COMMENT 'receivables-燃油费率',
ADD COLUMN `receivable_fuel_weight_method` varchar(50) DEFAULT NULL COMMENT 'receivables-燃油费取重方式',
ADD COLUMN `receivable_tc_rate` decimal(10,2) DEFAULT NULL COMMENT 'receivables-TC费率',
ADD COLUMN `receivable_front_warehouse_rate` decimal(10,2) DEFAULT NULL COMMENT 'receivables-前置仓费率',
ADD COLUMN `receivable_remark` text DEFAULT NULL COMMENT 'receivables-应收备注',
ADD COLUMN `pay_intl_air_buy_order_fee` decimal(10,2) DEFAULT NULL COMMENT 'payables.intl_air-买单费/单',
ADD COLUMN `pay_intl_air_document_fee` decimal(10,2) DEFAULT NULL COMMENT 'payables.intl_air-单证费/单',
ADD COLUMN `pay_intl_air_fuel_rate` decimal(10,2) DEFAULT NULL COMMENT 'payables.intl_air-燃油费率',
ADD COLUMN `pay_intl_air_fuel_weight_method` varchar(50) DEFAULT NULL COMMENT 'payables.intl_air-燃油费取重方式',
ADD COLUMN `pay_intl_air_tc_rate` decimal(10,2) DEFAULT NULL COMMENT 'payables.intl_air-TC费率',
ADD COLUMN `pay_intl_air_front_warehouse_rate` decimal(10,2) DEFAULT NULL COMMENT 'payables.intl_air-前置仓费率',
ADD COLUMN `pay_customs_buy_order_fee` decimal(10,2) DEFAULT NULL COMMENT 'payables.customs-买单费/单',
ADD COLUMN `pay_customs_document_fee` decimal(10,2) DEFAULT NULL COMMENT 'payables.customs-单证费/单',
ADD COLUMN `pay_ground_tc_rate` decimal(10,2) DEFAULT NULL COMMENT 'payables.ground-TC费率',
ADD COLUMN `pay_trucking_flight_doc_no` varchar(100) DEFAULT NULL COMMENT 'payables.trucking-主单号',
ADD COLUMN `pay_trucking_origin_city` varchar(100) DEFAULT NULL COMMENT 'payables.trucking-始发城市',
ADD COLUMN `pay_trucking_destination_city` varchar(100) DEFAULT NULL COMMENT 'payables.trucking-目的城市',
ADD COLUMN `pay_dom_air_volume` decimal(10,3) DEFAULT NULL COMMENT 'payables.dom_air-体积';
