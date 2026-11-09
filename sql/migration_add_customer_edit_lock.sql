-- 存量库发布前执行一次；前提：两台状态字段及consignment_operation_logs表已存在。
-- 新库使用已更新建表SQL/ORM，不重复执行ADD COLUMN。
-- 保留客服status原有语义：客服保存提交为1，但费用尚未保存提交时仍可编辑。
ALTER TABLE `consignment_infos`
    ADD COLUMN `edit_locked` tinyint(1) NOT NULL DEFAULT 0
    COMMENT '费用保存提交后锁定客服编辑，不随费用暂存解除' AFTER `status`;

-- 当前费用已提交，或存在真实费用保存记录，均锁定。
-- 第二种情况包括费用保存过后又暂存为0的单据，不因再次暂存解锁。
-- 未发现费用提交依据的记录保留默认0；客服status=1本身不再构成锁定依据。
-- 不改变状态、金额、标签、业务更新时间，不虚构历史操作。
UPDATE `consignment_infos` AS customer
SET edit_locked = 1, updated_at = customer.updated_at
WHERE customer.edit_locked = 0
  AND (
      EXISTS (
          SELECT 1 FROM `cost_consignments` AS cost
          WHERE cost.id = customer.id AND cost.status = 1
      )
      OR EXISTS (
          SELECT 1 FROM `consignment_operation_logs` AS logs
          WHERE logs.consignment_id = customer.id
            AND logs.source = 'cost_service' AND logs.action = 'save'
      )
  );
