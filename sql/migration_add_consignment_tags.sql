-- 两台勾选项独立存储；上线前执行一次，不更改历史业务数据。
-- NULL 表示历史未保存勾选项，接口统一返回 []；不会根据费用值推测勾选状态。
ALTER TABLE `consignment_registrations`
ADD COLUMN `customer_tags` JSON DEFAULT NULL COMMENT '客服页面勾选项，最多5项';

ALTER TABLE `consignment_infos`
ADD COLUMN `customer_tags` JSON DEFAULT NULL COMMENT '客服页面勾选项，最多5项';

ALTER TABLE `cost_registrations`
ADD COLUMN `expense_tags` JSON DEFAULT NULL COMMENT '费用页面勾选项，最多7项';

ALTER TABLE `cost_consignments`
ADD COLUMN `expense_tags` JSON DEFAULT NULL COMMENT '费用页面勾选项，最多7项';
