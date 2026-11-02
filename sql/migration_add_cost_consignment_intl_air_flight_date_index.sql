-- 存量库执行一次：费用列表改用应付款项-国际空运航班日期筛选，增加范围查询索引。
-- 不变更业务字段或数据，保留原货主航班日期索引供既有查询/导出使用。
-- 全新库通过已更新的建表SQL或ORM建表时已包含索引，不再执行此增量脚本。
ALTER TABLE `cost_consignments`
    ADD INDEX `idx_pay_intl_air_flight_date` (`pay_intl_air_flight_date`);
