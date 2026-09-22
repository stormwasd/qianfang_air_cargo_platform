-- 为费用登记台货主托运信息的航班日期筛选增加索引。
ALTER TABLE `cost_consignments`
ADD INDEX `idx_flight_date` (`flight_date`);
