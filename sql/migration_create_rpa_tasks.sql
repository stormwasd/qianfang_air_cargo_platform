-- RPA任务队列表
-- 执行时间：2026-01-16
-- 用于存储待执行的RPA任务，实现任务队列功能

CREATE TABLE IF NOT EXISTS `rpa_tasks` (
    `id` BIGINT NOT NULL COMMENT '任务ID',
    `task_type` VARCHAR(50) NOT NULL COMMENT '任务类型（SHENZHEN_AIR_WAYBILL_EXECUTE/SHENZHEN_AIR_WAYBILL_VOID/CHINA_SOUTHERN_AIR_BOOKING_EXECUTE/CHINA_SOUTHERN_AIR_BOOKING_CANCEL/CHINA_SOUTHERN_AIR_DIRECT_INVOICE）',
    `target_type` VARCHAR(20) NOT NULL COMMENT '目标类型（waybill/booking）',
    `target_id` BIGINT NOT NULL COMMENT '目标ID（运单ID或订舱ID）',
    `batch_id` BIGINT NULL COMMENT '批量执行批次ID',
    `params` TEXT NOT NULL COMMENT 'RPA调用参数（JSON格式）',
    `queue_params` TEXT NULL COMMENT '队列参数（JSON格式，用于存储需要创建的队列信息）',
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '任务状态（pending/running/success/failed/timeout）',
    `priority` INT NOT NULL DEFAULT 1 COMMENT '优先级（数值越大越优先，默认1）',
    `work_uuid` VARCHAR(100) NULL COMMENT 'RPA返回的workUuid',
    `job_uuid` VARCHAR(100) NULL COMMENT 'RPA的jobUuid',
    `result` TEXT NULL COMMENT '执行结果（JSON格式）',
    `error_message` TEXT NULL COMMENT '错误信息',
    `created_by` BIGINT NULL COMMENT '创建用户ID',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（中国时间UTC+8）',
    `started_at` DATETIME(6) NULL COMMENT '开始执行时间',
    `finished_at` DATETIME(6) NULL COMMENT '完成时间',
    PRIMARY KEY (`id`),
    INDEX `idx_task_type` (`task_type`),
    INDEX `idx_target_type` (`target_type`),
    INDEX `idx_target_id` (`target_id`),
    INDEX `idx_batch_id` (`batch_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_priority` (`priority`),
    INDEX `idx_work_uuid` (`work_uuid`),
    INDEX `idx_created_by` (`created_by`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_status_priority_created` (`status`, `priority`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RPA任务队列表';

