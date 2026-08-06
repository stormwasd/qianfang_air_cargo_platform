-- 删除费用登记台表格中废弃的应收代理 (receivable_agent) 字段

ALTER TABLE `cost_registrations` DROP COLUMN `receivable_agent`;
ALTER TABLE `cost_consignments` DROP COLUMN `receivable_agent`;
