def time_str_to_minutes(time_str: str) -> int:
    """将 'HH:MM' 转换为一天中的分钟数"""
    try:
        h, m = map(int, time_str.split(':'))
        return h * 60 + m
    except:
        return 0
