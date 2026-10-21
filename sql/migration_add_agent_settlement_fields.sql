-- 现有数据库升级：执行一次；不需要重新执行建表脚本。
ALTER TABLE `air_financial_audit_data`
  ADD COLUMN `agent_settlement_status` INT DEFAULT 0 COMMENT '空运代理对账结算状态: 0=未结算, 1=已结算',
  ADD COLUMN `agent_settlement_auditor_id` BIGINT DEFAULT NULL COMMENT '空运代理对账结算操作人ID',
  ADD COLUMN `agent_settlement_auditor_name` VARCHAR(255) DEFAULT NULL COMMENT '空运代理对账结算操作人',
  ADD COLUMN `agent_settlement_time` DATETIME DEFAULT NULL COMMENT '空运代理对账结算时间',
  ADD INDEX `ix_agent_settlement_status` (`agent_settlement_status`);
