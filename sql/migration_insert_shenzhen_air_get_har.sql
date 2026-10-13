-- 新增“深航获取har”RPA流程定义。
-- 可重复执行：task_name 已存在时同步为本次指定的流程元数据。
INSERT INTO `task_processes` (
    `id`, `task_name`, `chinese_name`, `process_detail_uuid`, `version`,
    `process_param`, `created_at`, `updated_at`
)
VALUES (
    FLOOR(RAND() * 900000000000000000 + 100000000000000000),
    'SHENZHEN_AIR_GET_HAR',
    '深航获取har',
    '9d55ee2fbd0460f44c1dd1c47f5f7e32',
    '0.0.2',
    '{"system_url":"https://www.kinggo.com/main"}',
    NOW(),
    NOW()
)
ON DUPLICATE KEY UPDATE
    `chinese_name` = VALUES(`chinese_name`),
    `process_detail_uuid` = VALUES(`process_detail_uuid`),
    `version` = VALUES(`version`),
    `process_param` = VALUES(`process_param`),
    `updated_at` = NOW();

-- 执行后还需在机器人管理中为目标机器人分配 SHENZHEN_AIR_GET_HAR 权限；
-- 保存机器人配置时，后端会自动生成/同步对应的 robot_jobs 记录。
