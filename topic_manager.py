import json
import os
import random
from datetime import datetime
from typing import Dict, List, Optional, Literal
from astrbot.api import logger

ChatType = Literal["group", "private"]

class TopicManager:
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.context = plugin_instance.context
        self.config = plugin_instance.config
        self.enable_context = self.config.get("enable_context_history", True)
        
        self.group_preset_file = plugin_instance.get_resource_path("resources/preset_topics_group.json")
        self.private_preset_file = plugin_instance.get_resource_path("resources/preset_topics_private.json")
        
        self.group_preset_topics = self._load_preset_topics(self.group_preset_file)
        self.private_preset_topics = self._load_preset_topics(self.private_preset_file)
        
        # 加载自定义主题列表
        self.custom_topics = self.config.get("custom_topics", [])
        if not self.custom_topics:
            self.custom_topics = [
                "美食",
                "天气",
                "原神"
            ]
            logger.info("未配置自定义主题，使用默认主题列表")
    
    def _load_preset_topics(self, filepath: str) -> List[str]:
        if not os.path.exists(filepath):
            logger.warning(f"预置话题文件 {filepath} 不存在，使用空列表")
            return []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception as e:
            logger.error(f"加载预置话题失败 {filepath}: {e}")
            return []
    
    def get_preset_topic(self, chat_type: ChatType) -> str:
        """获取预置话题（最终消息内容）"""
        topics = self.group_preset_topics if chat_type == "group" else self.private_preset_topics
        if not topics:
            return "今天想聊点什么呢？"
        return random.choice(topics)
    
    def get_custom_topic(self) -> Optional[str]:
        """获取随机一个自定义话题关键词（如“美食”、“原神”），供LLM生成具体内容"""
        if not self.custom_topics:
            logger.warning("自定义主题列表为空，降级到预设话题")
            return None
        return random.choice(self.custom_topics)
    
    def get_knowledge_topic(self, chat_type: ChatType) -> str:
        """基于知识/时间生成话题描述（提供给LLM）"""
        now = datetime.now()
        month = now.month
        hour = now.hour
        
        if 3 <= month <= 5:
            season = "春天"
        elif 6 <= month <= 8:
            season = "夏天"
        elif 9 <= month <= 11:
            season = "秋天"
        else:
            season = "冬天"
        
        if 5 <= hour < 12:
            time_desc = "早晨"
        elif 12 <= hour < 14:
            time_desc = "中午"
        elif 14 <= hour < 18:
            time_desc = "下午"
        elif 18 <= hour < 22:
            time_desc = "傍晚"
        else:
            time_desc = "夜晚"
        
        if chat_type == "group":
            return f"现在是{season}的{time_desc}，请主动和大家聊聊季节变化、天气或最近的节日。"
        else:
            return f"现在是{season}的{time_desc}，请主动和你聊聊季节变化、天气或最近的节日。"
    
    def get_history_topic(self, chat_type: ChatType, chat_id: str, limit: int = 10) -> Optional[str]:
        """基于历史消息，让 LLM 自己判断该聊什么话题（去掉调侃，只允许延续或开启新话题）"""
        if not self.enable_context:
            return None
        try:
            history = self.context.get_chat_history(chat_id, limit)
            if not history:
                return None
            recent_msgs = []
            for msg in history[-5:]:
                if hasattr(msg, 'is_send_by_self') and msg.is_send_by_self:
                    continue
                sender = getattr(msg, 'sender_name', '用户')
                content = getattr(msg, 'content', str(msg))
                recent_msgs.append(f"{sender}: {content}")
            if not recent_msgs:
                return None
            
            # 构建上下文摘要，让 LLM 自己决定话题方向（只允许延续或开启新话题）
            context_text = "\n".join(recent_msgs)
            if chat_type == "group":
                return (
                    f"以下是最近的群聊内容：\n{context_text}\n\n"
                    "请根据以上内容，判断现在应该聊什么话题最合适。"
                    "你可以延续当前话题，或者开启一个新话题。"
                    "请用一句话描述你要聊的话题方向，不要直接生成最终消息。"
                )
            else:
                return (
                    f"以下是你们最近的对话内容：\n{context_text}\n\n"
                    "请根据以上内容，判断现在应该聊什么话题最合适。"
                    "你可以延续当前话题，或者开启一个新话题。"
                    "请用一句话描述你要聊的话题方向，不要直接生成最终消息。"
                )
        except Exception as e:
            logger.error(f"获取历史消息失败: {e}")
            return None
    
    def select_source(self, weights: Dict[str, int]) -> str:
        items = list(weights.keys())
        probs = list(weights.values())
        return random.choices(items, weights=probs, k=1)[0]
