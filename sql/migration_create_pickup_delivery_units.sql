-- 创建提货单位管理表
CREATE TABLE `pickup_units` (
  `id` bigint(20) NOT NULL COMMENT '主键ID',
  `pickup_code` varchar(50) DEFAULT NULL COMMENT '提货单位编码',
  `pickup_name` varchar(200) NOT NULL COMMENT '提货单位名称',
  `contact_person` varchar(50) NOT NULL COMMENT '联系人',
  `contact_phone` varchar(20) NOT NULL COMMENT '联系电话',
  `settlement_method` tinyint(4) NOT NULL COMMENT '结算方式',
  `creator_id` bigint(20) NOT NULL COMMENT '创建人ID',
  `creator_name` varchar(50) NOT NULL COMMENT '创建人名称',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `ix_pickup_units_pickup_code` (`pickup_code`),
  KEY `ix_pickup_units_pickup_name` (`pickup_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提货单位管理表';

-- 创建派送单位管理表
CREATE TABLE `delivery_units` (
  `id` bigint(20) NOT NULL COMMENT '主键ID',
  `delivery_code` varchar(50) DEFAULT NULL COMMENT '派送单位编码',
  `delivery_name` varchar(200) NOT NULL COMMENT '派送单位名称',
  `contact_person` varchar(50) NOT NULL COMMENT '联系人',
  `contact_phone` varchar(20) NOT NULL COMMENT '联系电话',
  `settlement_method` tinyint(4) NOT NULL COMMENT '结算方式',
  `creator_id` bigint(20) NOT NULL COMMENT '创建人ID',
  `creator_name` varchar(50) NOT NULL COMMENT '创建人名称',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `ix_delivery_units_delivery_code` (`delivery_code`),
  KEY `ix_delivery_units_delivery_name` (`delivery_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='派送单位管理表';
