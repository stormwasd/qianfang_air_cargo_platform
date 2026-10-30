-- 上线前执行一次。保留四张业务/模板表原编号列，不删除历史编号。
ALTER TABLE `consignment_operation_logs`
ADD COLUMN `internal_doc_id` varchar(100) DEFAULT NULL COMMENT '内部单据ID快照';

-- 仅使用仍存在单据上的真实编号补齐历史快照，不创造历史操作或编号。
-- 与接口一致：同ID费用单据编号优先，其次客服编号。
UPDATE `consignment_operation_logs` AS logs
LEFT JOIN `cost_consignments` AS cost ON cost.id = logs.consignment_id
LEFT JOIN `consignment_infos` AS customer ON customer.id = logs.consignment_id
SET logs.internal_doc_id = COALESCE(NULLIF(cost.internal_doc_id, ''), NULLIF(customer.internal_doc_id, ''))
WHERE logs.internal_doc_id IS NULL
  AND (NULLIF(cost.internal_doc_id, '') IS NOT NULL OR NULLIF(customer.internal_doc_id, '') IS NOT NULL);
