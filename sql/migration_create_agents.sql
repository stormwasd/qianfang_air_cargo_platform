-- 创建代理管理表
CREATE TABLE `agents` (
  `id` bigint(20) NOT NULL COMMENT '主键ID',
  `agent_code` varchar(50) DEFAULT NULL COMMENT '代理编码',
  `agent_type` tinyint(4) NOT NULL COMMENT '代理类型',
  `agent_name` varchar(200) NOT NULL COMMENT '代理名称',
  `contact_person` varchar(50) NOT NULL COMMENT '联系人',
  `contact_phone` varchar(20) NOT NULL COMMENT '联系电话',
  `document_fee` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '制单费',
  `settlement_method` tinyint(4) NOT NULL COMMENT '结算方式',
  `creator_id` bigint(20) NOT NULL COMMENT '创建人ID',
  `creator_name` varchar(50) NOT NULL COMMENT '创建人名称',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `ix_agents_agent_code` (`agent_code`),
  KEY `ix_agents_agent_name` (`agent_name`),
  KEY `ix_agents_agent_type` (`agent_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='代理管理表';
