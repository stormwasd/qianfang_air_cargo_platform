-- 周期性 RPA 任务按机器人维度的入队时间打卡表。
-- 用于确保唐翼重启流程严格遵从 RPA_TANGYI_RESTART_INTERVAL_SECONDS。
CREATE TABLE IF NOT EXISTS `rpa_recurring_task_schedule_states` (
  `id` BIGINT NOT NULL COMMENT '记录ID',
  `robot_id` BIGINT NOT NULL COMMENT '机器人记录ID',
  `task_type` VARCHAR(100) NOT NULL COMMENT '周期性RPA任务类型',
  `last_enqueued_at` DATETIME(6) NOT NULL COMMENT '最近一次入队时间（中国时间UTC+8）',
  `created_at` DATETIME(6) NOT NULL COMMENT '创建时间',
  `updated_at` DATETIME(6) NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_robot_recurring_task_type` (`robot_id`, `task_type`),
  KEY `idx_robot_id` (`robot_id`),
  KEY `idx_task_type` (`task_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='周期性RPA任务调度状态表';
