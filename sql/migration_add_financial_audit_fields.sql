ALTER TABLE `peer_road_departure_manual_data`
ADD COLUMN `financial_audit_status` int(11) DEFAULT '0' COMMENT '财务审核状态: 0=未审, 1=暂存, 2=已审' AFTER `audit_time`,
ADD COLUMN `financial_auditor_id` bigint(20) DEFAULT NULL COMMENT '财务审核人ID' AFTER `financial_audit_status`,
ADD COLUMN `financial_auditor_name` varchar(255) DEFAULT NULL COMMENT '财务审核人' AFTER `financial_auditor_id`,
ADD COLUMN `financial_audit_time` datetime DEFAULT NULL COMMENT '财务审核时间' AFTER `financial_auditor_name`;

ALTER TABLE `peer_air_departure_manual_data`
ADD COLUMN `financial_audit_status` int(11) DEFAULT '0' COMMENT '财务审核状态: 0=未审, 1=暂存, 2=已审' AFTER `audit_time`,
ADD COLUMN `financial_auditor_id` bigint(20) DEFAULT NULL COMMENT '财务审核人ID' AFTER `financial_audit_status`,
ADD COLUMN `financial_auditor_name` varchar(255) DEFAULT NULL COMMENT '财务审核人' AFTER `financial_auditor_id`,
ADD COLUMN `financial_audit_time` datetime DEFAULT NULL COMMENT '财务审核时间' AFTER `financial_auditor_name`;
