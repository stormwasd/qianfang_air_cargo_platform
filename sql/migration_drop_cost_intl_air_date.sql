-- 删除费用登记台“应付款项-国际空运”中废弃的托运日期字段。
-- 应用代码部署完成后执行，历史值将随列删除。

ALTER TABLE `cost_registrations` DROP COLUMN `pay_intl_air_date`;
ALTER TABLE `cost_consignments` DROP COLUMN `pay_intl_air_date`;
