-- 插入两个新的RPA流程配置到 task_processes 表
-- 1. 深航订舱-计飞时间-集装器数据获取
INSERT INTO `task_processes` (`id`, `task_name`, `chinese_name`, `process_detail_uuid`, `version`, `process_param`, `created_at`, `updated_at`)
VALUES (
    FLOOR(RAND() * 900000000000000000 + 100000000000000000),
    'SHENZHEN_AIR_BILLING_TIME_CONTAINER',
    '深航订舱-计飞时间-集装器数据获取',
    'fbf660cc3aa24ac7d664ce7ab55273e5',
    'v0.0.3',
    '{"system_url":"https://www.kinggo.com/main","system_account":"szxfdh002","waybill_number_8":"61475831"}',
    NOW(),
    NOW()
);

-- 2. 深航订舱-过机-装机数据获取
INSERT INTO `task_processes` (`id`, `task_name`, `chinese_name`, `process_detail_uuid`, `version`, `process_param`, `created_at`, `updated_at`)
VALUES (
    FLOOR(RAND() * 900000000000000000 + 100000000000000000),
    'SHENZHEN_AIR_TRANSIT_LOADING',
    '深航订舱-过机-装机数据获取',
    'f81468b2e2b6cbf262163ae8506159bb',
    'v0.0.1',
    '{"system_url":"https://www.kinggo.com/main","system_account":"szxfdh002"}',
    NOW(),
    NOW()
);
