-- 插入新的RPA流程配置到 task_processes 表
-- 深航订舱-批复数据获取
INSERT INTO `task_processes` (`id`, `task_name`, `chinese_name`, `process_detail_uuid`, `version`, `process_param`, `created_at`, `updated_at`)
VALUES (
    FLOOR(RAND() * 900000000000000000 + 100000000000000000),
    'SHENZHEN_AIR_APPROVAL_DATA',
    '深航订舱-批复数据获取',
    '9e80ba8fbf57fb312b8da70691f087fb',
    '0.0.1',
    '{"system_url":"https://www.kinggo.com/main","system_account":"szxfdh002","login_password":"fengde123456..","flight_date":"2026-06-09"}',
    NOW(),
    NOW()
);
