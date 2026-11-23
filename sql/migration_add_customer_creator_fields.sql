-- 为客户管理表增加创建人相关字段
ALTER TABLE customers
ADD COLUMN creator_id BIGINT(20) DEFAULT NULL COMMENT '创建人ID',
ADD COLUMN creator_name VARCHAR(50) DEFAULT NULL COMMENT '创建人名称';
