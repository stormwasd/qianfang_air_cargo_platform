-- 南航直连订舱持久化任务扩展
-- 在已有数据库执行一次；新建数据库由 Base.metadata.create_all 自动创建字段。
ALTER TABLE `rpa_tasks`
    ADD COLUMN `batch_id` BIGINT NULL COMMENT '批量执行批次ID' AFTER `target_id`,
    ADD INDEX `idx_batch_id` (`batch_id`);

