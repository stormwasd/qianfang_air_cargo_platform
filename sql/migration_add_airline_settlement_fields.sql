ALTER TABLE `air_financial_audit_data`
ADD COLUMN `airline_settlement_status` int(11) DEFAULT 0 COMMENT '航司对账结算状态: 0=未结算, 1=已结算' AFTER `financial_audit_time`,
ADD COLUMN `airline_settlement_auditor_id` bigint(20) DEFAULT NULL COMMENT '航司对账结算操作人ID' AFTER `airline_settlement_status`,
ADD COLUMN `airline_settlement_auditor_name` varchar(255) DEFAULT NULL COMMENT '航司对账结算操作人' AFTER `airline_settlement_auditor_id`,
ADD COLUMN `airline_settlement_time` datetime DEFAULT NULL COMMENT '航司对账结算时间' AFTER `airline_settlement_auditor_name`,
ADD INDEX `idx_airline_settlement_status` (`airline_settlement_status`);
