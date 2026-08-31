-- 南航接口直连订舱任务表（与通用 rpa_tasks 完全隔离）
CREATE TABLE IF NOT EXISTS `china_southern_air_booking_tasks` (
    `id` BIGINT NOT NULL COMMENT '任务ID',
    `batch_id` BIGINT NOT NULL COMMENT '批量执行批次ID',
    `booking_id` BIGINT NOT NULL COMMENT '订舱ID',
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '任务状态（pending/running/success/failed）',
    `priority` INT NOT NULL DEFAULT 1 COMMENT '优先级',
    `params` TEXT NOT NULL COMMENT '任务参数（JSON格式）',
    `result` TEXT NULL COMMENT '执行结果（JSON格式）',
    `error_message` TEXT NULL COMMENT '错误信息',
    `error_details` TEXT NULL COMMENT '结构化错误详情（JSON格式）',
    `created_by` BIGINT NULL COMMENT '创建用户ID',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `started_at` DATETIME(6) NULL,
    `finished_at` DATETIME(6) NULL,
    PRIMARY KEY (`id`),
    INDEX `idx_csa_booking_task_batch_id` (`batch_id`),
    INDEX `idx_csa_booking_task_booking_id` (`booking_id`),
    INDEX `idx_csa_booking_task_status` (`status`),
    INDEX `idx_csa_booking_task_status_priority_created` (`status`, `priority`, `created_at`),
    INDEX `idx_csa_booking_task_batch_booking` (`batch_id`, `booking_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='南航接口直连订舱任务表';

-- 清理上一版误加到通用 rpa_tasks 的字段（不存在时不执行，兼容新旧环境）。
SET @drop_direct_booking_batch_index = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'rpa_tasks'
              AND INDEX_NAME = 'idx_batch_id'
        ),
        'ALTER TABLE `rpa_tasks` DROP INDEX `idx_batch_id`',
        'SELECT 1'
    )
);
PREPARE drop_direct_booking_batch_index_stmt FROM @drop_direct_booking_batch_index;
EXECUTE drop_direct_booking_batch_index_stmt;
DEALLOCATE PREPARE drop_direct_booking_batch_index_stmt;

SET @drop_direct_booking_batch_column = (
    SELECT IF(
        EXISTS(
            SELECT 1 FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'rpa_tasks'
              AND COLUMN_NAME = 'batch_id'
        ),
        'ALTER TABLE `rpa_tasks` DROP COLUMN `batch_id`',
        'SELECT 1'
    )
);
PREPARE drop_direct_booking_batch_column_stmt FROM @drop_direct_booking_batch_column;
EXECUTE drop_direct_booking_batch_column_stmt;
DEALLOCATE PREPARE drop_direct_booking_batch_column_stmt;
