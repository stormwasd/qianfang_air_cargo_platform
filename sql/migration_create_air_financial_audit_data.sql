CREATE TABLE `air_financial_audit_data` (
  `id` bigint(20) NOT NULL COMMENT '主键ID',
  `source_type` varchar(20) NOT NULL COMMENT '来源类型: shenzhen_air / china_southern_air / peer_air',
  `source_id` bigint(20) NOT NULL COMMENT '来源主表ID',
  
  -- 人工填写字段（应付）
  `payable_telegraph_cost` varchar(50) DEFAULT NULL COMMENT '电报费/电报成本(应付-人工填写)',
  `payable_other_fee_remark` varchar(500) DEFAULT NULL COMMENT '其他费用说明(应付-人工填写)',
  
  -- 人工填写字段（应收）
  `receivable_consignee_phone` varchar(100) DEFAULT NULL COMMENT '收货电话(应收-人工填写, 仅同行空运)',
  `receivable_consignee_unit` varchar(255) DEFAULT NULL COMMENT '收货单位(应收-人工填写, 仅同行空运)',
  `receivable_other_fee_remark` varchar(500) DEFAULT NULL COMMENT '其他费用说明(应收-人工填写)',
  `receivable_pickup_fee` varchar(50) DEFAULT NULL COMMENT '上门提货费(应收-人工填写)',
  `receivable_carrier_deduction` varchar(50) DEFAULT NULL COMMENT '承运扣款(应收-人工填写)',
  `receivable_pickup_method` varchar(100) DEFAULT NULL COMMENT '提货方式(应收-人工填写)',
  `receivable_collection_payment` varchar(50) DEFAULT NULL COMMENT '代收货款(应收-人工填写)',
  `receivable_remark` varchar(500) DEFAULT NULL COMMENT '备注(应收-人工填写)',
  
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
