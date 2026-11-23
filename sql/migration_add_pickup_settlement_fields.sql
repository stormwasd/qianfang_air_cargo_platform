-- 添加提货单位对账相关的状态字段
ALTER TABLE air_financial_audit_data
ADD COLUMN pickup_settlement_status int(11) DEFAULT 0 COMMENT '提货单位对账结算状态: 0=未结算, 1=已结算' AFTER airline_settlement_time,
ADD COLUMN pickup_settlement_auditor_id bigint(20) DEFAULT NULL COMMENT '提货单位对账结算操作人ID' AFTER pickup_settlement_status,
ADD COLUMN pickup_settlement_auditor_name varchar(255) DEFAULT NULL COMMENT '提货单位对账结算操作人' AFTER pickup_settlement_auditor_id,
ADD COLUMN pickup_settlement_time datetime DEFAULT NULL COMMENT '提货单位对账结算时间' AFTER pickup_settlement_auditor_name;

-- 添加索引加速按结算状态查询
ALTER TABLE air_financial_audit_data
ADD INDEX idx_pickup_settle_status (pickup_settlement_status);
