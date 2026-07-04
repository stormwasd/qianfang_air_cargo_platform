CREATE TABLE `air_financial_audit_data` (
  `id` bigint(20) NOT NULL COMMENT '主键ID',
  `source_type` varchar(20) NOT NULL COMMENT '来源类型: shenzhen_air / china_southern_air / peer_air',
  `source_id` bigint(20) NOT NULL COMMENT '来源主表ID',
  
  -- 应收与应付板块的自定义修改覆盖数据JSON
  `payable_data` json DEFAULT NULL COMMENT '应付修改后的全部数据 JSON',
  `receivable_data` json DEFAULT NULL COMMENT '应收修改后的全部数据 JSON',
  
  -- 财务审核状态
  `financial_audit_status` int(11) DEFAULT '0' COMMENT '财务审核状态: 0=未审, 1=暂存, 2=已审',
  `financial_auditor_id` bigint(20) DEFAULT NULL COMMENT '财务审核人ID',
  `financial_auditor_name` varchar(255) DEFAULT NULL COMMENT '财务审核人',
  `financial_audit_time` datetime DEFAULT NULL COMMENT '财务审核时间',
  
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ux_source` (`source_type`, `source_id`),
  KEY `ix_financial_audit_status` (`financial_audit_status`),
  KEY `ix_source_id` (`source_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='空运财务审核扩展数据表';
