-- 向 robot_jobs 表添加 bot_uuid 字段，记录生成 Job 时绑定的物理机器人 UUID
-- 执行时间：2026-05-06

ALTER TABLE `robot_jobs` ADD COLUMN `bot_uuid` VARCHAR(100) NULL DEFAULT NULL COMMENT '生成时使用的机器人UUID' AFTER `process_detail_uuid`;
