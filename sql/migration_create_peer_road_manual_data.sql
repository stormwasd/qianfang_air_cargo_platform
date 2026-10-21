CREATE TABLE `peer_road_departure_manual_data` (
  `id` bigint(20) NOT NULL COMMENT '主键ID',
  `consignment_note_id` bigint(20) NOT NULL COMMENT '关联 consignment_notes.id',
  `audit_status` int(11) DEFAULT '0' COMMENT '审核状态: 0=未审, 1=暂存, 2=已审',
  `auditor_id` bigint(20) DEFAULT NULL COMMENT '审核人ID',
  `auditor_name` varchar(255) DEFAULT NULL COMMENT '审核人',
  `audit_time` datetime DEFAULT NULL COMMENT '审核时间',
  `agent_settlement_status` int DEFAULT 0 COMMENT '汽运代理结算状态: 0=未结算, 1=已结算',
  `agent_settlement_auditor_id` bigint DEFAULT NULL COMMENT '汽运代理结算操作人ID',
  `agent_settlement_auditor_name` varchar(255) DEFAULT NULL COMMENT '汽运代理结算操作人',
  `agent_settlement_time` datetime DEFAULT NULL COMMENT '汽运代理结算时间',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_peer_road_manual_consignment_id` (`consignment_note_id`),
  KEY `ix_peer_road_departure_manual_data_agent_settlement_status` (`agent_settlement_status`),
  KEY `ix_peer_road_departure_manual_data_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='同行汽运出港审核数据表';
