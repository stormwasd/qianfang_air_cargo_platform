ALTER TABLE shenzhen_air_departure_manual_data 
ADD COLUMN cargo_type VARCHAR(50) DEFAULT NULL COMMENT '货物类型' AFTER customer_name;
