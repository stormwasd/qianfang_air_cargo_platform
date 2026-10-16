-- 深航KingGo直连开单独立任务表；不修改现有RPA任务。
CREATE TABLE IF NOT EXISTS shenzhen_air_direct_waybill_queue_lock (
    id INT NOT NULL PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO shenzhen_air_direct_waybill_queue_lock (id) VALUES (1);

CREATE TABLE IF NOT EXISTS shenzhen_air_direct_waybill_tasks (
    id BIGINT NOT NULL PRIMARY KEY,
    waybill_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    priority INT NOT NULL DEFAULT 10,
    created_by BIGINT NULL,
    request_data TEXT NOT NULL,
    stage VARCHAR(20) NOT NULL DEFAULT 'preparing',
    candidate_waybill_number VARCHAR(50) NULL,
    result TEXT NULL,
    error_message TEXT NULL,
    created_at DATETIME NOT NULL,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    INDEX ix_shenzhen_air_direct_waybill_tasks_id (id),
    INDEX ix_shenzhen_air_direct_waybill_tasks_waybill_id (waybill_id),
    INDEX ix_shenzhen_air_direct_waybill_tasks_status (status),
    INDEX ix_shenzhen_air_direct_waybill_tasks_created_by (created_by),
    INDEX ix_shenzhen_air_direct_waybill_tasks_created_at (created_at),
    INDEX idx_shenzhen_direct_waybill_task_status_created (status, created_at),
    INDEX idx_shenzhen_direct_waybill_task_waybill_status (waybill_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
