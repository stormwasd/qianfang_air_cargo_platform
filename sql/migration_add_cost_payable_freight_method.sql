-- 新增费用登记台国际空运、国内空运应付款项运费计算方式字段
ALTER TABLE `cost_registrations`
    ADD COLUMN `pay_intl_air_freight_method` varchar(50) DEFAULT NULL COMMENT '国际空运-运费计算方式' AFTER `pay_intl_air_rate`,
    ADD COLUMN `pay_dom_air_freight_method` varchar(50) DEFAULT NULL COMMENT '国内空运-运费计算方式' AFTER `pay_dom_air_rate`;

ALTER TABLE `cost_consignments`
    ADD COLUMN `pay_intl_air_freight_method` varchar(50) DEFAULT NULL COMMENT '国际空运-运费计算方式' AFTER `pay_intl_air_rate`,
    ADD COLUMN `pay_dom_air_freight_method` varchar(50) DEFAULT NULL COMMENT '国内空运-运费计算方式' AFTER `pay_dom_air_rate`;
