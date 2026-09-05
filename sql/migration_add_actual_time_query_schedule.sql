-- 实飞时间首次查询延迟及失败重试的持久化调度时间
ALTER TABLE `shenzhen_air_billing_time_containers`
  ADD COLUMN `next_actual_time_query_at` DATETIME NULL COMMENT '下一次查询实飞时间时间';

ALTER TABLE `csa_lalamove_information`
  ADD COLUMN `next_actual_time_query_at` DATETIME NULL COMMENT '下一次查询实飞时间时间';
