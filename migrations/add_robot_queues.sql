-- 机器人队列配置表：每个机器人 × 每个任务类型 × 每个队列 key = 一条记录
CREATE TABLE robot_queues (
    id BIGINT PRIMARY KEY COMMENT '记录ID',
    robot_id BIGINT NOT NULL COMMENT '机器人记录ID（FK robots.id）',
    task_name VARCHAR(100) NOT NULL COMMENT '任务名称（如 SHENZHEN_AIR_WAYBILL_EXECUTE）',
    queue_key VARCHAR(100) NOT NULL COMMENT '队列用途标识（如 waybill_number, freight_rate）',
    queue_name VARCHAR(200) NOT NULL COMMENT '队列名称（全局唯一，带机器人标识）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_robot_task_queue (robot_id, task_name, queue_key),
    INDEX idx_robot_id (robot_id),
    INDEX idx_task_name (task_name)
) COMMENT '机器人队列配置表';
