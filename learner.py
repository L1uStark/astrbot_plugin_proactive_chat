import random
from datetime import datetime, timedelta
from astrbot.api import logger

class SilenceLearner:
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.context = plugin_instance.context
        self.config = plugin_instance.config
        
        self.learned_params = {
            "silence_wait": None,
            "phase1_duration": None,
            "phase1_prob": None,
            "phase2_duration": None,
            "phase2_prob": None,
            "example_phrases": []
        }
        
    async def daily_learn(self, chat_type: str = "group"):
        if not self.config.get("group_enabled", True):
            return
        
        now = datetime.now()
        since = now - timedelta(days=1)
        allowed_ids = self.config.get("group_allowed_ids", [])
        
        if not hasattr(self.plugin, 'proactive_scheduler'):
            logger.error("无法获取调度器实例，学习终止")
            return
        sessions = self.plugin.proactive_scheduler.group_sessions
        
        all_intervals = []
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
                
                if intervals:
                    all_intervals.extend(intervals)
                
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
        
        if all_intervals:
            avg_interval = sum(all_intervals) / len(all_intervals)
            if avg_interval < 600:
                self.learned_params["silence_wait"] = 5
                self.learned_params["phase1_duration"] = 20
                self.learned_params["phase1_prob"] = 0.2
            elif avg_interval < 1800:
                self.learned_params["silence_wait"] = 10
                self.learned_params["phase1_duration"] = 40
                self.learned_params["phase1_prob"] = 0.15
            else:
                self.learned_params["silence_wait"] = 20
                self.learned_params["phase1_duration"] = 60
                self.learned_params["phase1_prob"] = 0.1
        
        if all_examples:
            unique_examples = list(dict.fromkeys(all_examples))
            self.learned_params["example_phrases"] = unique_examples[-20:]
        
        # 更新可视化状态
        status_text = f"[学习状态 - {now.strftime('%Y-%m-%d %H:%M')}]\n"
        status_text += f"沉默等待: {self.learned_params['silence_wait']}分钟 | "
        status_text += f"阶段1: {self.learned_params['phase1_duration']}分钟 | "
        status_text += f"概率1: {self.learned_params['phase1_prob']} | "
        status_text += f"阶段2: {self.learned_params['phase2_duration']}分钟 | "
        status_text += f"概率2: {self.learned_params['phase2_prob']}\n"
        if self.learned_params.get("example_phrases"):
            status_text += "风格例句:\n"
            for phrase in self.learned_params["example_phrases"][-5:]:
                status_text += f"- {phrase}\n"
        else:
            status_text += "暂无风格例句"
        
        self.plugin.config["learning_status"] = status_text
        logger.info("学习状态已更新到 WebUI 配置面板")
    
    def get_dynamic_param(self, key: str, default):
        val = self.learned_params.get(key)
        if val is not None:
            return val
        return default
