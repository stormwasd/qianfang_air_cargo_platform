-- 增加客户管理新字段
ALTER TABLE customers
ADD COLUMN customer_code VARCHAR(50) DEFAULT NULL COMMENT '客户编码',
ADD COLUMN minimum_ticket_fee DECIMAL(10, 2) DEFAULT NULL COMMENT '最低票费用',
ADD COLUMN document_fee DECIMAL(10, 2) DEFAULT NULL COMMENT '制单费',
ADD COLUMN minimum_ticket_fee_condition DECIMAL(10, 2) DEFAULT NULL COMMENT '最低票收取条件',
ADD COLUMN document_fee_condition DECIMAL(10, 2) DEFAULT NULL COMMENT '制单费收取条件',
ADD COLUMN weight_range_operation_fee_rate JSON DEFAULT NULL COMMENT '重量范围_操作费费率',
ADD COLUMN cargo_type_transit_fee_rate JSON DEFAULT NULL COMMENT '货物类型_过站费费率',
ADD COLUMN settlement_cycle TINYINT DEFAULT NULL COMMENT '结算周期(1=周结, 2=半月结, 3=月结, 4=现结)',
ADD COLUMN is_invoiced TINYINT(1) DEFAULT 0 COMMENT '是否开票',
DROP COLUMN settlement_method;

-- 增加索引
CREATE INDEX ix_customers_customer_code ON customers(customer_code);
