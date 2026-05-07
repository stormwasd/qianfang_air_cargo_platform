-- 给 rpa_tasks 表新增 location 字段（区域路由：shenzhen_air / china_southern_air）
ALTER TABLE rpa_tasks ADD COLUMN location VARCHAR(50) NULL COMMENT '任务所属区域（shenzhen_air/china_southern_air），用于匹配机器人location';
CREATE INDEX idx_rpa_tasks_location ON rpa_tasks (location);
