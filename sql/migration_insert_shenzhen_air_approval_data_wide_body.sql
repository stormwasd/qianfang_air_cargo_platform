INSERT INTO `task_processes` (`id`, `task_name`, `chinese_name`, `process_detail_uuid`, `version`, `process_param`, `created_at`, `updated_at`)
VALUES (
    (SELECT * FROM (SELECT COALESCE(MAX(id), 0) + 1 FROM `task_processes`) AS temp),
    'SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY',
    '深航订舱-批复数据获取-宽体',
    '4965f72ad9c53cb5a7db0542e3bb6f4e',
    '0.0.1',
    '{"system_url":"https://www.kinggo.com/main","system_account":"szxfdh002","login_password":"fengde123456..","flight_date":"2026-06-10"}',
    NOW(),
    NOW()
);
