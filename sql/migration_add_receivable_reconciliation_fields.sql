-- 已有库升级：部署新版应用前执行一次。只加列和索引，不修改原应付结算状态。
-- 两条 ALTER 均需成功；MySQL DDL 自动提交，中断后先核对已有列，勿重复执行。
ALTER TABLE `air_financial_audit_data`
  ADD COLUMN `receivable_airline_settlement_status` INT DEFAULT 0 COMMENT '应收航司结算状态: 0=未结算, 1=已结算',
  ADD COLUMN `receivable_airline_settlement_auditor_id` BIGINT DEFAULT NULL COMMENT '应收航司结算操作人ID',
  ADD COLUMN `receivable_airline_settlement_auditor_name` VARCHAR(255) DEFAULT NULL COMMENT '应收航司结算操作人',
  ADD COLUMN `receivable_airline_settlement_time` DATETIME DEFAULT NULL COMMENT '应收航司结算时间',
  ADD COLUMN `receivable_pickup_settlement_status` INT DEFAULT 0 COMMENT '应收提货单位结算状态: 0=未结算, 1=已结算',
  ADD COLUMN `receivable_pickup_settlement_auditor_id` BIGINT DEFAULT NULL COMMENT '应收提货单位结算操作人ID',
  ADD COLUMN `receivable_pickup_settlement_auditor_name` VARCHAR(255) DEFAULT NULL COMMENT '应收提货单位结算操作人',
  ADD COLUMN `receivable_pickup_settlement_time` DATETIME DEFAULT NULL COMMENT '应收提货单位结算时间',
  ADD COLUMN `receivable_delivery_settlement_status` INT DEFAULT 0 COMMENT '应收派送单位结算状态: 0=未结算, 1=已结算',
  ADD COLUMN `receivable_delivery_settlement_auditor_id` BIGINT DEFAULT NULL COMMENT '应收派送单位结算操作人ID',
  ADD COLUMN `receivable_delivery_settlement_auditor_name` VARCHAR(255) DEFAULT NULL COMMENT '应收派送单位结算操作人',
  ADD COLUMN `receivable_delivery_settlement_time` DATETIME DEFAULT NULL COMMENT '应收派送单位结算时间',
  ADD COLUMN `receivable_agent_settlement_status` INT DEFAULT 0 COMMENT '应收空运代理结算状态: 0=未结算, 1=已结算',
  ADD COLUMN `receivable_agent_settlement_auditor_id` BIGINT DEFAULT NULL COMMENT '应收空运代理结算操作人ID',
  ADD COLUMN `receivable_agent_settlement_auditor_name` VARCHAR(255) DEFAULT NULL COMMENT '应收空运代理结算操作人',
  ADD COLUMN `receivable_agent_settlement_time` DATETIME DEFAULT NULL COMMENT '应收空运代理结算时间',
  ADD INDEX `ix_air_recv_airline_status` (`receivable_airline_settlement_status`),
  ADD INDEX `ix_air_recv_pickup_status` (`receivable_pickup_settlement_status`),
  ADD INDEX `ix_air_recv_delivery_status` (`receivable_delivery_settlement_status`),
  ADD INDEX `ix_air_recv_agent_status` (`receivable_agent_settlement_status`);

ALTER TABLE `peer_road_departure_manual_data`
  ADD COLUMN `receivable_agent_settlement_status` INT DEFAULT 0 COMMENT '应收汽运代理结算状态: 0=未结算, 1=已结算',
  ADD COLUMN `receivable_agent_settlement_auditor_id` BIGINT DEFAULT NULL COMMENT '应收汽运代理结算操作人ID',
  ADD COLUMN `receivable_agent_settlement_auditor_name` VARCHAR(255) DEFAULT NULL COMMENT '应收汽运代理结算操作人',
  ADD COLUMN `receivable_agent_settlement_time` DATETIME DEFAULT NULL COMMENT '应收汽运代理结算时间',
  ADD INDEX `ix_road_recv_agent_status` (`receivable_agent_settlement_status`);
