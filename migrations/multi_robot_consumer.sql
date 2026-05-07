-- 多机器人任务消费架构 - 数据库迁移
-- 执行时间: 2026-05-07

-- 1. 为 rpa_tasks 表添加 robot_id 字段（指定消费的机器人，NULL表示任意有权限的机器人可消费）
ALTER TABLE rpa_tasks ADD COLUMN robot_id BIGINT NULL COMMENT '指定消费的机器人ID（NULL=任意有权限的机器人消费）';
CREATE INDEX idx_rpa_tasks_robot_id ON rpa_tasks (robot_id);
