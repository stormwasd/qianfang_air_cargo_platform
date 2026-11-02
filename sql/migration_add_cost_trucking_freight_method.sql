-- 发布代码前在存量库执行一次：费用模板和单据新增汽运运费计算方式。
-- 历史值为NULL，不推断选项、不回算费用；客服复用现有financial_data JSON，无需加列。
-- 全新库使用已更新的建表SQL或ORM建表，不再执行此增量脚本。
ALTER TABLE `cost_registrations`
    ADD COLUMN `pay_trucking_freight_method` varchar(50) DEFAULT NULL COMMENT '汽运-运费计算方式' AFTER `pay_trucking_unit_price`;

ALTER TABLE `cost_consignments`
    ADD COLUMN `pay_trucking_freight_method` varchar(50) DEFAULT NULL COMMENT '汽运-运费计算方式' AFTER `pay_trucking_unit_price`;
