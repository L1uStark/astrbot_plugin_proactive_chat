import random
from datetime import datetime, timedelta
from astrbot.api import logger

class SilenceLearner:
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.context = plugin_instance.context
        self.config = plugin_instance.config
        
        # 按群存储学习参数：{ chat_id: { "silence_wait": 5, ... } }
        self.group_params: dict = {}
        # 全局例句库
        self.global_example_phrases: list = []
        
    async def daily_learn(self, chat_type: str = "group"):
        """每天分析过去24小时群聊，按群分别存储学习结果"""
        if not self.config.get("group_enabled", True):
            return
        
        now = datetime.now()
        since = now - timedelta(days=1)
        allowed_ids = self.config.get("group_allowed_ids", [])
        
        if not hasattr(self.plugin, 'proactive_scheduler'):
            logger.error("无法获取调度器实例，学习终止")
            return
        sessions = self.plugin.proactive_scheduler.group_sessions
        
        all_examples = []
        
        for chat_id, state in sessions.items():
            if allowed_ids and chat_id not in allowed_ids:
                continue
                
            try:
                history = await self.context.get_chat_history(chat_id, limit=200)
                if not history:
                    continue
                recent = [msg for msg in history if hasattr(msg, 'timestamp') and msg.timestamp >= since.timestamp()]
                if len(recent) < 10:
                    continue
                
                # 计算沉默间隔
                last_time = None
                intervals = []
                for msg in recent:
                    if getattr(msg, 'is_send_by_self', False):
                        continue
                    if last_time:
                        diff = msg.timestamp - last_time
                        if diff > 300:
                            intervals.append(diff)
                    last_time = msg.timestamp
                
                # 按群存储学习参数
                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    if avg_interval < 600:
                        self.group_params[chat_id] = {
                            "silence_wait": 5,
                            "phase1_duration": 20,
                            "phase1_prob": 0.2
                        }
                    elif avg_interval < 1800:
                        self.group_params[chat_id] = {
                            "silence_wait": 10,
                            "phase1_duration": 40,
                            "phase1_prob": 0.15
                        }
                    else:
                        self.group_params[chat_id] = {
                            "silence_wait": 20,
                            "phase1_duration": 60,
                            "phase1_prob": 0.1
                        }
                    logger.info(f"群 {chat_id} 学习完成：平均沉默间隔 {avg_interval/60:.1f} 分钟")
                
                # 收集例句
                last_time = None
                examples = []
                for msg in recent:
                    if getattr(msg, 'is_send_by_self', False):
                        continue
                    if last_time and (msg.timestamp - last_time) > 300:
                        content = getattr(msg, 'content', '') or getattr(msg, 'plain_text', '')
                        if content and len(content) > 2:
                            examples.append(content)
                    last_time = msg.timestamp
                
                if examples:
                    all_examples.extend(examples[-20:])
                
            except Exception as e:
                logger.error(f"学习群 {chat_id} 失败: {e}")
        
        # 更新全局例句
        if all_examples:
            unique_examples = list(dict.fromkeys(all_examples))
            self.global_example_phrases = unique_examples[-20:]
        
        # 更新可视化状态
        status_lines = ["[学习状态 - " + now.strftime('%Y-%m-%d %H:%M') + "]"]
        for chat_id, params in self.group_params.items():
            status_lines.append(f"群 {chat_id}: 等待={params['silence_wait']}min, 阶段1={params['phase1_duration']}min, 概率1={params['phase1_prob']}")
        if self.global_example_phrases:
            status_lines.append("风格例句:")
            for phrase in self.global_example_phrases[-5:]:
                status_lines.append(f"- {phrase}")
        self.plugin.config["learning_status"] = "\n".join(status_lines)
        logger.info("学习状态已更新到 WebUI 配置面板")
    
    def get_dynamic_param(self, key: str, default):
        """兼容旧接口，始终返回 None"""
        return None
    
    def get_dynamic_param_for_group(self, chat_id: str, key: str, default):
        """获取指定群的学习参数，未学习时返回默认值"""
        if chat_id in self.group_params:
            return self.group_params[chat_id].get(key, default)
        return default
    
    def get_example_phrases(self) -> list:
        """获取全局风格例句"""
        return self.global_example_phrases
