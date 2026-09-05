-- 出港跟踪任务延迟执行/限次重试及携程起飞时间字段
ALTER TABLE `rpa_tasks`
  ADD COLUMN `scheduled_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '计划可执行时间（中国时间）',
  ADD COLUMN `attempt_count` INT NOT NULL DEFAULT 0 COMMENT '已消费次数',
  ADD COLUMN `max_attempts` INT NOT NULL DEFAULT 1 COMMENT '最大消费次数',
  ADD INDEX `idx_status_scheduled_at` (`status`, `scheduled_at`);

ALTER TABLE `shenzhen_air_billing_time_containers`
  ADD COLUMN `planned_time` VARCHAR(50) NULL COMMENT '预飞时间（携程）',
  ADD COLUMN `actual_time` VARCHAR(50) NULL COMMENT '实飞时间（携程）',
  ADD COLUMN `actual_time_attempts` VARCHAR(20) NOT NULL DEFAULT '0' COMMENT '实飞时间查询次数';

ALTER TABLE `csa_lalamove_information`
  ADD COLUMN `actual_time` VARCHAR(50) NULL COMMENT '实飞时间（携程）',
  ADD COLUMN `actual_time_attempts` VARCHAR(20) NOT NULL DEFAULT '0' COMMENT '实飞时间查询次数';

ALTER TABLE `shenzhen_air_booking_exports`
  ADD COLUMN `departure_tracking_completed` VARCHAR(1) NOT NULL DEFAULT '0' COMMENT '出港明细是否已完成抓取';

ALTER TABLE `china_southern_air_approval_data`
  ADD COLUMN `departure_tracking_completed` VARCHAR(1) NOT NULL DEFAULT '0' COMMENT '出港明细是否已完成抓取';
