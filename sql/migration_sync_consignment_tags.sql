-- 前提：已经执行 migration_add_consignment_tags.sql。
-- 存量库发布代码前执行一次；新库建表/ORM已含以下四列，不重复加列。
ALTER TABLE `consignment_registrations`
ADD COLUMN `expense_tags` JSON DEFAULT NULL COMMENT '费用页面勾选项，最多7项';

ALTER TABLE `consignment_infos`
ADD COLUMN `expense_tags` JSON DEFAULT NULL COMMENT '费用页面勾选项，最多7项';

ALTER TABLE `cost_registrations`
ADD COLUMN `customer_tags` JSON DEFAULT NULL COMMENT '客服页面勾选项，最多5项';

ALTER TABLE `cost_consignments`
ADD COLUMN `customer_tags` JSON DEFAULT NULL COMMENT '客服页面勾选项，最多5项';

-- 补齐已流转单据的同名标签，NULL表示费用侧未保存，[]表示明确清空而须保留。
-- 不从customer_tags猜测expense_tags，不复制唯一模板，不同步尚未提交的客服草稿。
-- 保留业务更新时间，避免纯回填改变列表顺序或看起来发生新的用户操作。
UPDATE `cost_consignments` AS cost
INNER JOIN `consignment_infos` AS customer ON customer.id = cost.id
SET cost.customer_tags = customer.customer_tags, cost.updated_at = cost.updated_at
WHERE (cost.customer_tags IS NULL OR JSON_TYPE(cost.customer_tags) = 'NULL')
  AND JSON_TYPE(customer.customer_tags) = 'ARRAY'
  AND customer.status IN (1, 2);

UPDATE `cost_consignments` AS cost
INNER JOIN `consignment_infos` AS customer ON customer.id = cost.id
SET cost.expense_tags = customer.expense_tags, cost.updated_at = cost.updated_at
WHERE (cost.expense_tags IS NULL OR JSON_TYPE(cost.expense_tags) = 'NULL')
  AND JSON_TYPE(customer.expense_tags) = 'ARRAY'
  AND customer.status IN (1, 2);
