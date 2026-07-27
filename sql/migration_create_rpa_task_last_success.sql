-- ----------------------------------------------------------------
-- 迁移脚本：创建 RPA 任务最后成功执行打卡表 (rpa_task_last_success)
-- 用于支持深/南航订舱批复跟踪与出港跟踪等列表的 data_update_time 展示
-- ----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `rpa_task_last_success` (
  `task_type` VARCHAR(100) NOT NULL COMMENT 'RPA任务类型 (RPATaskType)',
  `last_success_at` DATETIME(6) NOT NULL COMMENT '最后一次成功执行时间（中国时间UTC+8）',
  `updated_at` DATETIME(6) NOT NULL COMMENT '记录更新时间（中国时间UTC+8）',
  PRIMARY KEY (`task_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RPA任务最后成功执行打卡表';
