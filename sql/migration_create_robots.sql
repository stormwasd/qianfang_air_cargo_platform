-- 机器人管理表
-- 执行时间：2026-05-02
-- 用于存储RPA机器人的配置信息，实现机器人可配置化管理

CREATE TABLE IF NOT EXISTS `robots` (
    `id` BIGINT NOT NULL COMMENT '机器人记录ID（雪花算法）',
    `robot_id` VARCHAR(500) NOT NULL COMMENT '机器人ID（加密后存储）',
    `name` VARCHAR(200) NOT NULL COMMENT '机器人名称',
    `location` VARCHAR(200) NOT NULL COMMENT '机器人所在位置',
    `task_permissions` TEXT NOT NULL COMMENT '可执行任务权限列表（JSON数组，如["SHENZHEN_AIR_WAYBILL_EXECUTE","DOCUMENT_PRINT"]）',
    `extra_config` TEXT NULL COMMENT '机器人其他配置（JSON对象，包含深航账号密码、打印机服务、唐翼程序地址等）',
    `status` TINYINT NOT NULL DEFAULT 1 COMMENT '机器人状态（1=启用，0=未启用）',
    `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间（中国时间UTC+8）',
    `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间（中国时间UTC+8）',
    PRIMARY KEY (`id`),
    UNIQUE INDEX `idx_robot_id` (`robot_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='机器人管理表';
