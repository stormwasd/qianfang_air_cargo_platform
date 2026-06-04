-- 创建托运书表 (Consignment Notes)
CREATE TABLE IF NOT EXISTS `consignment_notes` (
    `id` bigint(20) NOT NULL COMMENT '托运书ID',
    `transport_type` varchar(10) NOT NULL COMMENT '托运方式：0=空运，1=汽运',
    `company_name` varchar(100) DEFAULT NULL COMMENT '代理公司名称',
    `customer_name` varchar(100) DEFAULT NULL COMMENT '客户名称',
    `consignment_date` date DEFAULT NULL COMMENT '托运日期（空运的航班日期，汽运的托运日期）',
    `destination` varchar(100) DEFAULT NULL COMMENT '目的站/终点城市',
    `flight_number` varchar(100) DEFAULT NULL COMMENT '航班号（空运特有）',
    `airline` varchar(100) DEFAULT NULL COMMENT '航司（空运特有）',
    `form_data` text NOT NULL COMMENT '托运单动态业务数据（JSON格式）',
    `creator_id` varchar(50) DEFAULT NULL COMMENT '制单人ID',
    `creator_name` varchar(100) DEFAULT NULL COMMENT '制单人姓名',
    `created_at` datetime NOT NULL COMMENT '创建时间/制单时间',
    `updated_at` datetime NOT NULL COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_transport_type` (`transport_type`),
    KEY `idx_consignment_date` (`consignment_date`),
    KEY `idx_company_name` (`company_name`),
    KEY `idx_customer_name` (`customer_name`),
    KEY `idx_destination` (`destination`),
    KEY `idx_flight_number` (`flight_number`),
    KEY `idx_airline` (`airline`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='托运书表';
