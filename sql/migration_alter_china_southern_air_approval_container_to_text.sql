-- 扩大南航批复数据所在容器字段，支持保存多组集装器及重量信息
ALTER TABLE `china_southern_air_approval_data`
  MODIFY COLUMN `container` TEXT DEFAULT NULL COMMENT '所在容器';
