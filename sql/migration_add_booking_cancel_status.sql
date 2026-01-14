-- 为bookings表添加退舱状态字段
-- 执行时间：2026-01-14

ALTER TABLE `bookings` 
ADD COLUMN `booking_cancel_status` VARCHAR(20) NOT NULL DEFAULT '0' COMMENT '退舱状态（数据字典值：0=未退舱，1=退舱中，2=退舱失败，3=退舱成功）' AFTER `rpa_work_uuid`,
ADD INDEX `idx_booking_cancel_status` (`booking_cancel_status`);

