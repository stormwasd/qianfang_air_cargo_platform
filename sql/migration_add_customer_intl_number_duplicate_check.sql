-- 存量库发布前执行：客服国际空运主单号近30天查重。
-- 互斥键只串行化同号校验事务，不是运单、不占用号码，不构成永久唯一限制。
CREATE TABLE IF NOT EXISTS `consignment_number_guards` (
    `number_hash` varchar(64) NOT NULL COMMENT '规范化国际空运主单号的SHA256，用于事务行锁',
    PRIMARY KEY (`number_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客服国际空运主单号查重事务互斥键';

-- 索引语句仅执行一次；已存在同名索引或以created_at开头的索引时跳过此ALTER。
-- 不增加业务字段、不回填JSON、不修改已有重复数据或业务更新时间。
ALTER TABLE `consignment_infos`
    ADD INDEX `ix_consignment_infos_created_at` (`created_at`);
