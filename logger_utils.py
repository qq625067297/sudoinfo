import os
import logging
from functools import wraps

# 全局默认日志器名称（确保所有方法使用同一个核心实例）
DEFAULT_LOG_NAME = "core_package"


def setup_logger(log_name=DEFAULT_LOG_NAME, log_file=None, log_level=logging.INFO):
    """初始化并返回一个共享的日志器

    Args:
        log_name (str): 日志器名称（单例标识）
        log_file (str): 自定义日志文件路径（None 时自动生成）
        log_level (int): 日志级别（如 logging.DEBUG）
    Returns:
        logging.Logger: 全局共享的日志器实例
    """
    logger = logging.getLogger(log_name)
    logger.setLevel(log_level)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    # 自动生成默认日志路径（如果未指定）
    if not log_file:
        log_dir = os.path.join("logs", "core_runtime")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{log_name}.log")

    # 文件处理器（输出到文件）
    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 控制台处理器（可选）
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter("%(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def log_decorator(logger=None):
    """自动绑定日志器的装饰器工厂"""
    def actual_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 自动获取全局日志器（如果未显式传入）
            _logger = logger or logging.getLogger(DEFAULT_LOG_NAME)
            _logger.info(f"执行函数: {func.__name__}")
            try:
                result = func(*args, **kwargs)
                _logger.debug(f"函数 {func.__name__} 返回: {result}")
                return result
            except Exception as e:
                _logger.error(f"函数 {func.__name__} 异常: {str(e)}", exc_info=True)
                raise
        return wrapper
    return actual_decorator
