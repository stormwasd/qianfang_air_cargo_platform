"""
深航订舱批复数据预警服务
1. 按时间间隔触发（如每10分钟）
2. 按固定时间点触发（如每天18:00）
扫描 shenzhen_air_approval_data 和 shenzhen_air_approval_wide_body_data 表，
对 parent_id 不为空且 status='ss' 的子记录进行订舱/批复数量对比，
发现不一致则通过企业微信Webhook推送预警消息。
"""

import asyncio
import threading
import traceback
import httpx
from datetime import datetime
from typing import Optional, List, Tuple

from app.config import settings
from app.database import SessionLocal


class ShenzhenAirApprovalAlertService:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[ShenzhenAirApprovalAlert] 已启动深航订舱批复预警服务")

    def stop(self) -> None:
        self._stop_event.set()
        print("[ShenzhenAirApprovalAlert] 已停止深航订舱批复预警服务")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        finally:
            loop.close()

    async def _async_main(self) -> None:
        """主循环：同时处理间隔触发和定时触发"""
        interval = getattr(settings, "ALERT_SHENZHEN_AIR_APPROVAL_INTERVAL_SECONDS", 600)
        fixed_times_str = getattr(settings, "ALERT_SHENZHEN_AIR_APPROVAL_FIXED_TIMES", "18:00")

        # 解析固定时间点列表
        fixed_times: List[str] = []
        if fixed_times_str and fixed_times_str.strip():
            fixed_times = [t.strip() for t in fixed_times_str.split(",") if t.strip()]

        # 记录已触发的定时时间点（避免同一分钟内重复触发）
        triggered_fixed_times: set = set()

        # 间隔计数器
        elapsed = 0

        while not self._stop_event.is_set():
            try:
                now = datetime.now()
                current_time_str = now.strftime("%H:%M")
                current_date_str = now.strftime("%Y-%m-%d")

                # 日期变更时重置已触发记录
                date_key = current_date_str
                if hasattr(self, "_last_date") and self._last_date != date_key:
                    triggered_fixed_times.clear()
                self._last_date = date_key

                # --- 定时触发检查 ---
                if current_time_str in fixed_times and current_time_str not in triggered_fixed_times:
                    triggered_fixed_times.add(current_time_str)
                    print(f"[ShenzhenAirApprovalAlert] 定时触发（{current_time_str}），开始扫描...")
                    await self._scan_and_alert()

                # --- 间隔触发检查 ---
                if interval and interval > 0:
                    elapsed += 5  # 每次循环 sleep 5 秒
                    if elapsed >= interval:
                        elapsed = 0
                        print(f"[ShenzhenAirApprovalAlert] 间隔触发（每{interval}秒），开始扫描...")
                        await self._scan_and_alert()

            except Exception as e:
                print(f"[ShenzhenAirApprovalAlert] 主循环异常: {repr(e)}\n{traceback.format_exc()}")

            await asyncio.sleep(5)

    async def _scan_and_alert(self) -> None:
        """扫描数据库并发送预警"""
        db = SessionLocal()
        try:
            from app.models.shenzhen_air_approval import ShenzhenAirApprovalData, ShenzhenAirApprovalWideBodyData
            from datetime import timedelta

            total_count = 0
            abnormal_count = 0
            abnormal_details: List[str] = []
            
            tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

            # ===== 1. 扫描窄体机表 (shenzhen_air_approval_data) =====
            # 先找明天航班的父级ID
            narrow_parent_ids = db.query(ShenzhenAirApprovalData.id).filter(
                ShenzhenAirApprovalData.parent_id.is_(None),
                ShenzhenAirApprovalData.flight_date == tomorrow_str
            ).subquery()

            narrow_records = db.query(ShenzhenAirApprovalData).filter(
                ShenzhenAirApprovalData.parent_id.in_(narrow_parent_ids),
                ShenzhenAirApprovalData.status == "ss"
            ).all()

            for record in narrow_records:
                total_count += 1
                if self._is_narrow_body_abnormal(record):
                    abnormal_count += 1
                    # 获取父级信息（航班号）用于展示
                    parent = db.query(ShenzhenAirApprovalData).filter(
                        ShenzhenAirApprovalData.id == record.parent_id
                    ).first()
                    flight_number = parent.flight_number if parent else "未知航班"
                    
                    pairs_info = [
                        ("F订/批", record.f_booking, record.f_approval),
                        ("C订/批", record.c_booking, record.c_approval),
                        ("其他订/批", record.other_booking, record.other_approval)
                    ]
                    detail_str = self._build_detail_string(pairs_info)
                    if detail_str:
                        abnormal_details.append(f"   [{flight_number}] - {detail_str}")

            # ===== 2. 扫描宽体机表 (shenzhen_air_approval_wide_body_data) =====
            wide_parent_ids = db.query(ShenzhenAirApprovalWideBodyData.id).filter(
                ShenzhenAirApprovalWideBodyData.parent_id.is_(None),
                ShenzhenAirApprovalWideBodyData.flight_date == tomorrow_str
            ).subquery()

            wide_records = db.query(ShenzhenAirApprovalWideBodyData).filter(
                ShenzhenAirApprovalWideBodyData.parent_id.in_(wide_parent_ids),
                ShenzhenAirApprovalWideBodyData.status == "ss"
            ).all()

            for record in wide_records:
                total_count += 1
                if self._is_wide_body_abnormal(record):
                    abnormal_count += 1
                    parent = db.query(ShenzhenAirApprovalWideBodyData).filter(
                        ShenzhenAirApprovalWideBodyData.id == record.parent_id
                    ).first()
                    flight_number = parent.flight_number if parent else "未知航班"
                    
                    pairs_info = [
                        ("板订/批", record.board_booking, record.board_approval),
                        ("箱订/批", record.box_booking, record.box_approval)
                    ]
                    detail_str = self._build_detail_string(pairs_info)
                    if detail_str:
                        abnormal_details.append(f"   [{flight_number}] - {detail_str}")

            normal_count = total_count - abnormal_count

            # ===== 3. 构造消息并发送 =====
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            message_lines = [
                f"深航订舱批复预警 ({now_str})",
                f"━━━━━━━━━━━━━━━━━━━━",
                f"订舱数量：{total_count}单",
                f"批复正常：{normal_count}单",
                f"批复异常：{abnormal_count}单",
            ]

            if abnormal_count > 0:
                message_lines.append("")
                message_lines.append("异常明细：")
                # 最多展示前20条，防止消息过长
                for detail in abnormal_details[:20]:
                    message_lines.append(detail)
                if len(abnormal_details) > 20:
                    message_lines.append(f"  ...等共{len(abnormal_details)}条")

            message = "\n".join(message_lines)
            await self._send_wechat_message(message)

            print(f"[ShenzhenAirApprovalAlert] 扫描完成 - 总计:{total_count}, 正常:{normal_count}, 异常:{abnormal_count}")

        except Exception as e:
            print(f"[ShenzhenAirApprovalAlert] 扫描异常: {repr(e)}\n{traceback.format_exc()}")
        finally:
            db.close()

    @staticmethod
    def _safe_to_float(value) -> Optional[float]:
        """安全地将字段值转为浮点数，用于数值比较"""
        if value is None or str(value).strip() == "":
            return None
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _is_zero(val) -> bool:
        """判断值是否为0或空"""
        if val is None or str(val).strip() == "":
            return True
        try:
            return float(str(val).strip()) == 0
        except ValueError:
            return False

    def _build_detail_string(self, pairs_info: List[Tuple[str, str, str]]) -> str:
        """构造非 0/0 的详情字符串"""
        parts = []
        for label, b, a in pairs_info:
            if self._is_zero(b) and self._is_zero(a):
                continue
            parts.append(f"{label}:{b}/{a}")
        return ", ".join(parts)

    def _is_narrow_body_abnormal(self, record) -> bool:
        """
        判断窄体机记录是否异常：
        f_booking vs f_approval、c_booking vs c_approval、other_booking vs other_approval
        任意一对数值不相等即为异常
        """
        pairs = [
            (record.f_booking, record.f_approval),
            (record.c_booking, record.c_approval),
            (record.other_booking, record.other_approval),
        ]
        for booking_val, approval_val in pairs:
            b = self._safe_to_float(booking_val)
            a = self._safe_to_float(approval_val)
            # 两个都是 None/空 视为正常（无数据）
            if b is None and a is None:
                continue
            # 一方有值一方没值，或数值不等，均视为异常
            if b != a:
                return True
        return False

    def _is_wide_body_abnormal(self, record) -> bool:
        """
        判断宽体机记录是否异常：
        board_booking vs board_approval、box_booking vs box_approval
        任意一对数值不相等即为异常
        """
        pairs = [
            (record.board_booking, record.board_approval),
            (record.box_booking, record.box_approval),
        ]
        for booking_val, approval_val in pairs:
            b = self._safe_to_float(booking_val)
            a = self._safe_to_float(approval_val)
            if b is None and a is None:
                continue
            if b != a:
                return True
        return False

    @staticmethod
    async def _send_wechat_message(content: str) -> None:
        """通过企业微信Webhook发送文本消息"""
        webhook_url = settings.WECHAT_WEBHOOK_URL
        if not webhook_url:
            print("[ShenzhenAirApprovalAlert] 未配置企业微信Webhook地址，跳过发送")
            return

        payload = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(webhook_url, json=payload)
                response.raise_for_status()
                result = response.json()
                if result.get("errcode") != 0:
                    print(f"[ShenzhenAirApprovalAlert] 企业微信发送失败: {result.get('errmsg', '未知错误')}")
                else:
                    print(f"[ShenzhenAirApprovalAlert] 预警消息已发送至企业微信群")
            except Exception as e:
                print(f"[ShenzhenAirApprovalAlert] 发送企业微信消息异常: {repr(e)}")


# 全局单例
shenzhen_air_approval_alert = ShenzhenAirApprovalAlertService()
