-- 南航订舱完整联系人提交标记；先执行此迁移，再部署使用该字段的后端。
-- MySQL：历史记录无法确认当时是否向南航提交完整信息，统一默认 0，不按当前配置回填。
-- API 返回 JSON boolean；本字段只由服务端维护，不接受前端写入。
ALTER TABLE `bookings`
    ADD COLUMN `has_complete_contact_info` TINYINT(1) NOT NULL DEFAULT 0
    COMMENT '南航直连订舱成功时是否已提交完整收发货人信息'
    AFTER `master_airwaybill_number`;
