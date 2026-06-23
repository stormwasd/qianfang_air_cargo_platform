CREATE TABLE IF NOT EXISTS `csa_loading_alert_tasks` (
  `id` bigint(20) NOT NULL,
  `approval_data_id` bigint(20) NOT NULL COMMENT '关联 china_southern_air_approval_data.id',
  `waybill_number` varchar(100) NOT NULL COMMENT '运单号',
  `flight_date` varchar(50) NOT NULL COMMENT '航班日期',
  `planned_time` varchar(50) DEFAULT NULL COMMENT '预飞时间',
  `trigger_time` datetime NOT NULL COMMENT '触发时间（计飞时间-100分钟）',
  `status` varchar(50) DEFAULT 'pending' COMMENT '状态: pending/processing/processed/ignored',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_csa_loading_alert_tasks_approval_data_id` (`approval_data_id`),
  KEY `ix_csa_loading_alert_tasks_id` (`id`),
  KEY `ix_csa_loading_alert_tasks_waybill_number` (`waybill_number`),
  KEY `ix_csa_loading_alert_tasks_flight_date` (`flight_date`),
  KEY `ix_csa_loading_alert_tasks_status` (`status`),
  KEY `ix_csa_loading_alert_tasks_trigger_time` (`trigger_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='南航装机状态预警任务表';
