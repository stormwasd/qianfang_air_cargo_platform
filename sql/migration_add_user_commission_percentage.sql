-- 账号管理新增提成百分比字段；历史账号保留为空。
ALTER TABLE `users`
ADD COLUMN `commission_percentage` decimal(5,2) DEFAULT NULL COMMENT '提成百分比' AFTER `name`;
