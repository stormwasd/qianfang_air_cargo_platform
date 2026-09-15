-- 上线前执行；历史操作无法可靠还原，不回填虚构记录。
-- 不设置业务单据或用户外键，保证删除单据、删除账号后仍保留操作记录。
CREATE TABLE IF NOT EXISTS `consignment_operation_logs` (
    `id` bigint NOT NULL COMMENT '操作记录ID',
    `consignment_id` bigint NOT NULL COMMENT '两台共用单据ID',
    `source` varchar(32) NOT NULL COMMENT 'customer_service/cost_service',
    `action` varchar(16) NOT NULL COMMENT 'draft/save/void/delete',
    `operation_name` varchar(50) NOT NULL COMMENT '操作名称快照',
    `operator_id` bigint NOT NULL COMMENT '实际操作用户ID',
    `operator_name` varchar(50) NOT NULL COMMENT '操作时用户姓名快照',
    `operated_at` datetime NOT NULL COMMENT '操作时间（中国时间UTC+8）',
    PRIMARY KEY (`id`),
    KEY `idx_consignment_operation_time` (`consignment_id`, `operated_at`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客服及费用单据操作记录';
