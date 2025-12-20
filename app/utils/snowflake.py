"""
雪花算法ID生成器
生成唯一的长整型ID，适用于分布式系统
"""
import time
import threading


class SnowflakeGenerator:
    """
    雪花算法ID生成器
    
    64位ID结构：
    - 1位符号位（始终为0）
    - 41位时间戳（毫秒级）
    - 10位机器ID（5位数据中心ID + 5位机器ID）
    - 12位序列号
    """
    
    # 时间戳起始点：2024-01-01 00:00:00
    EPOCH = 1704067200000
    
    # 位分配
    TIMESTAMP_BITS = 41
    DATACENTER_ID_BITS = 5
    MACHINE_ID_BITS = 5
    SEQUENCE_BITS = 12
    
    # 最大值
    MAX_DATACENTER_ID = (1 << DATACENTER_ID_BITS) - 1
    MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1
    
    # 位移
    MACHINE_ID_SHIFT = SEQUENCE_BITS
    DATACENTER_ID_SHIFT = SEQUENCE_BITS + MACHINE_ID_BITS
    TIMESTAMP_SHIFT = SEQUENCE_BITS + MACHINE_ID_BITS + DATACENTER_ID_BITS
    
    def __init__(self, datacenter_id: int = 1, machine_id: int = 1):
        """
        初始化雪花算法生成器
        
        Args:
            datacenter_id: 数据中心ID (0-31)
            machine_id: 机器ID (0-31)
        """
        if datacenter_id > self.MAX_DATACENTER_ID or datacenter_id < 0:
            raise ValueError(f"datacenter_id必须在0-{self.MAX_DATACENTER_ID}之间")
        if machine_id > self.MAX_MACHINE_ID or machine_id < 0:
            raise ValueError(f"machine_id必须在0-{self.MAX_MACHINE_ID}之间")
        
        self.datacenter_id = datacenter_id
        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()
    
    def _current_timestamp(self) -> int:
        """获取当前时间戳（毫秒）"""
        return int(time.time() * 1000)
    
    def _wait_next_millis(self, last_timestamp: int) -> int:
        """等待下一毫秒"""
        timestamp = self._current_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self._current_timestamp()
        return timestamp
    
    def generate_id(self) -> int:
        """
        生成唯一ID
        
        Returns:
            64位长整型ID
        """
        with self.lock:
            timestamp = self._current_timestamp()
            
            # 时钟回拨处理
            if timestamp < self.last_timestamp:
                raise RuntimeError(
                    f"时钟回拨，拒绝生成ID。当前时间戳：{timestamp}，上次时间戳：{self.last_timestamp}"
                )
            
            # 同一毫秒内，序列号递增
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE
                # 序列号溢出，等待下一毫秒
                if self.sequence == 0:
                    timestamp = self._wait_next_millis(self.last_timestamp)
            else:
                # 新的毫秒，序列号重置
                self.sequence = 0
            
            self.last_timestamp = timestamp
            
            # 生成ID
            id_value = (
                ((timestamp - self.EPOCH) << self.TIMESTAMP_SHIFT) |
                (self.datacenter_id << self.DATACENTER_ID_SHIFT) |
                (self.machine_id << self.MACHINE_ID_SHIFT) |
                self.sequence
            )
            
            return id_value


# 全局单例生成器（默认数据中心ID=1，机器ID=1）
# 在生产环境中，应该从配置文件或环境变量读取
_generator = SnowflakeGenerator(datacenter_id=1, machine_id=1)


def generate_id() -> int:
    """
    生成唯一ID（使用全局生成器）
    
    Returns:
        64位长整型ID
    """
    return _generator.generate_id()


def get_generator(datacenter_id: int = 1, machine_id: int = 1) -> SnowflakeGenerator:
    """
    获取指定配置的生成器实例
    
    Args:
        datacenter_id: 数据中心ID
        machine_id: 机器ID
    
    Returns:
        SnowflakeGenerator实例
    """
    return SnowflakeGenerator(datacenter_id=datacenter_id, machine_id=machine_id)

