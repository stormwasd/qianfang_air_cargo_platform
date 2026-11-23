-- 创建公司账户表
CREATE TABLE `company_accounts` (
  `id` bigint(20) NOT NULL COMMENT '主键ID',
  `account_name` varchar(200) NOT NULL COMMENT '账户名',
  `account_number` varchar(100) NOT NULL COMMENT '账号',
  `bank_name` varchar(200) NOT NULL COMMENT '开户行',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公司账户表';
