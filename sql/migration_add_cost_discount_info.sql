-- 费用登记台新增折让信息。
-- 报关回扣字段仅从业务接口、ORM 映射及 Excel 中下线；历史数据库列暂时保留，避免迁移时丢失既有数据。

ALTER TABLE `cost_registrations`
    ADD COLUMN `discount_person` varchar(100) DEFAULT NULL COMMENT '折让人员' AFTER `pay_total`,
    ADD COLUMN `discount_fee` decimal(10,2) DEFAULT NULL COMMENT '折让费' AFTER `discount_person`;

ALTER TABLE `cost_consignments`
    ADD COLUMN `discount_person` varchar(100) DEFAULT NULL COMMENT '折让人员' AFTER `pay_total`,
    ADD COLUMN `discount_fee` decimal(10,2) DEFAULT NULL COMMENT '折让费' AFTER `discount_person`;
