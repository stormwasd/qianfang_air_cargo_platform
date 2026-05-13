-- 新增机器人 location 限制开关
-- 执行时间：2026-05-13
-- 默认 1（开启），保持兼容

ALTER TABLE `robots` ADD COLUMN `location_required` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用location区域限制（1=开启，0=关闭）' AFTER `location`;
