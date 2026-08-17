-- 为客服接单台进仓日期排序补充索引。
CREATE INDEX `idx_warehouse_entry_date`
    ON `consignment_infos` (`warehouse_entry_date`);
