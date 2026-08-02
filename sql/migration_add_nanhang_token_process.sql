-- 1. 创建南航 Token 存储表 nanhang_token
CREATE TABLE IF NOT EXISTS `nanhang_token` (
    `id` BIGINT NOT NULL COMMENT '记录ID',
    `robot_id` BIGINT DEFAULT NULL COMMENT '关联机器人ID（FK robots.id）',
    `token` TEXT NOT NULL COMMENT '南航Token数据',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间（UTC+8）',
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间（UTC+8）',
    PRIMARY KEY (`id`),
    KEY `idx_robot_id` (`robot_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='南航Token存储表';

-- 2. 插入新的 RPA 流程配置到 task_processes 表
INSERT INTO `task_processes` (`id`, `task_name`, `chinese_name`, `process_detail_uuid`, `version`, `process_param`, `created_at`, `updated_at`)
VALUES (
    FLOOR(RAND() * 900000000000000000 + 100000000000000000),
    'CHINA_SOUTHERN_AIR_GET_TOKEN',
    '南航获取token',
    'ccd69aab94b92dec70bd05dfd6f3aa21',
    '0.0.2',
    '{"system_url":"https://cargo.csair.com/tangb2gweb/order-management","queue_token_name":""}',
    NOW(),
    NOW()
);

-- 3. （说明与备用手工 SQL）关于 robot_queues：
-- 当在前端或通过 API (/api/v1/robots) 创建或修改机器人时，只要给机器人分配了 "CHINA_SOUTHERN_AIR_GET_TOKEN" 任务权限，
-- 后端 RobotJobService 将会自动在 robot_queues 表中插入专属队列配置。
-- 如需手工给某个现有机器人（假设机器人 id 为 123456789）写入队列，可参考以下 SQL：
-- INSERT INTO `robot_queues` (`id`, `robot_id`, `task_name`, `queue_key`, `queue_name`, `created_at`, `updated_at`)
-- VALUES (
--     FLOOR(RAND() * 900000000000000000 + 100000000000000000),
--     123456789,
--     'CHINA_SOUTHERN_AIR_GET_TOKEN',
--     'token_name',
--     'china_southern_air_get_token_queue_token_name_123456789',
--     NOW(),
--     NOW()
-- );
