import asyncio
import random
from datetime import datetime
from typing import Dict, Any, Literal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

from .utils import time_str_to_minutes
from .topic_manager import TopicManager
from .llm_client import LLMClient

logger = logging.getLogger(__name__)
ChatType = Literal["group", "private"]

class ProactiveScheduler:
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.context = plugin_instance.context
        self.config = plugin_instance.config
        self.scheduler = AsyncIOScheduler()
        
        self.group_origins: Dict[str, Any] = {}
        self.private_origins: Dict[str, Any] = {}
        self.group_last_chat: Dict[str, datetime] = {}
        self.private_last_chat: Dict[str, datetime] = {}
        self.group_last_msg: Dict[str, datetime] = {}
        self.private_last_msg: Dict[str, datetime] = {}
        
        self.topic_manager = TopicManager(plugin_instance)
        self._llm_client = None
    
    def _get_personality_text(self) -> str:
        """获取最终使用的人格：自定义 > 系统人设 > 默认"""
        custom = self.config.get("personality_custom", "").strip()
        if custom:
            return custom
        try:
            system_personality = self.context.get_personality()
            if system_personality and hasattr(system_personality, 'description') and system_personality.description:
                return system_personality.description
        except Exception as e:
            logger.debug(f"获取系统人设失败: {e}")
        return "一个友好的聊天机器人"
    
    def _get_llm_client(self):
        if self._llm_client is None:
            llm_provider = self.config.get("llm_provider", "")
            llm_api_key = self.config.get("llm_api_key", "")
            if not llm_provider or not llm_api_key:
                logger.info("未配置独立 LLM，将使用系统默认")
                return None
            personality_text = self._get_personality_text()
            self._llm_client = LLMClient(self.config, personality_text)
        return self._llm_client
    
    async def _generate_message_with_system_llm(self, topic: str, chat_type: ChatType) -> str:
        try:
            llm_provider = self.context.get_llm_provider()
            personality_text = self._get_personality_text()
            audience = "大家" if chat_type == "group" else "你"
            prompt = (
                f"你的人设：{personality_text}\n"
                f"根据话题「{topic}」生成一句主动聊天消息，对象是{audience}。"
                f"要求自然简短不超50字，不要加引号。"
            )
            response = await llm_provider.text_chat(prompt, system_prompt="你是一个聊天机器人")
            return response.strip()
        except Exception as e:
            logger.error(f"系统 LLM 生成失败: {e}")
            if chat_type == "group":
                return "今天天气不错，大家心情如何？"
            else:
                return "今天天气不错，你心情如何？"
    
    async def _send_proactive_message(self, origin, chat_id: str, chat_type: ChatType):
        if chat_type == "group":
            weights = self.config.get("group_topic_weights", {"history":40, "knowledge":35, "preset":25})
            source = self.topic_manager.select_source(weights)
        else:
            weights = self.config.get("private_topic_weights", {"history":50, "knowledge":30, "preset":20})
            source = self.topic_manager.select_source(weights)
        
        logger.info(f"为 {chat_type} {chat_id} 选择话题来源: {source}")
        
        topic = None
        if source == "preset":
            topic = self.topic_manager.get_preset_topic(chat_type)
        elif source == "knowledge":
            topic = self.topic_manager.get_knowledge_topic(chat_type)
        elif source == "history":
            topic = self.topic_manager.get_history_topic(chat_type, chat_id)
            if not topic:
                topic = self.topic_manager.get_preset_topic(chat_type)
        
        llm_client = self._get_llm_client()
        if llm_client:
            message = await llm_client.generate_response(topic, chat_type)
        else:
            message = await self._generate_message_with_system_llm(topic, chat_type)
        
        try:
            from astrbot.core.message.message_event import MessageChain
            chain = MessageChain().message(message)
            await self.context.send_message(origin, chain)
            if chat_type == "group":
                self.group_last_chat[chat_id] = datetime.now()
            else:
                self.private_last_chat[chat_id] = datetime.now()
            logger.info(f"向 {chat_type} {chat_id} 主动发送: {message}")
        except Exception as e:
            logger.error(f"发送主动消息失败: {e}")
    
    async def _check_and_trigger_for_type(self, chat_type: ChatType):
        enabled_key = f"{chat_type}_enabled"
        if not self.config.get(enabled_key, True):
            return
        
        now = datetime.now()
        start_key = f"{chat_type}_start_time"
        end_key = f"{chat_type}_end_time"
        start_min = time_str_to_minutes(self.config.get(start_key, "00:00"))
        end_min = time_str_to_minutes(self.config.get(end_key, "23:59"))
        now_min = now.hour * 60 + now.minute
        if not (start_min <= now_min <= end_min):
            return
        
        interval_key = f"{chat_type}_check_interval"
        jitter_key = f"{chat_type}_jitter"
        prob_key = f"{chat_type}_probability"
        min_interval_key = f"{chat_type}_min_interval"
        isolation_key = f"{chat_type}_isolation_time"
        allowed_key = f"{chat_type}_allowed_ids"
        
        base_interval = self.config.get(interval_key, 15)
        jitter = self.config.get(jitter_key, 5)
        prob = self.config.get(prob_key, 0.3)
        min_interval = self.config.get(min_interval_key, 60)
        isolation = self.config.get(isolation_key, 10)
        allowed_ids = self.config.get(allowed_key, [])
        
        origins_dict = self.group_origins if chat_type == "group" else self.private_origins
        last_chat_dict = self.group_last_chat if chat_type == "group" else self.private_last_chat
        last_msg_dict = self.group_last_msg if chat_type == "group" else self.private_last_msg
        
        for chat_id, origin in list(origins_dict.items()):
            if allowed_ids and chat_id not in allowed_ids:
                continue
            if random.random() > prob:
                continue
            
            last_chat = last_chat_dict.get(chat_id)
            if last_chat:
                minutes_since_chat = (now - last_chat).total_seconds() / 60
                if minutes_since_chat < min_interval:
                    continue
            
            last_msg = last_msg_dict.get(chat_id)
            if last_msg:
                minutes_since_msg = (now - last_msg).total_seconds() / 60
                if minutes_since_msg < isolation:
                    continue
            
            await self._send_proactive_message(origin, chat_id, chat_type)
    
    async def _check_and_trigger(self):
        await self._check_and_trigger_for_type("group")
        await self._check_and_trigger_for_type("private")
    
    def start(self):
        group_interval = self.config.get("group_check_interval", 15) * 60
        private_interval = self.config.get("private_check_interval", 20) * 60
        
        async def group_check():
            await self._check_and_trigger_for_type("group")
        async def private_check():
            await self._check_and_trigger_for_type("private")
        
        self.scheduler.add_job(group_check, 'interval', seconds=group_interval, id='proactive_group')
        self.scheduler.add_job(private_check, 'interval', seconds=private_interval, id='proactive_private')
        self.scheduler.start()
        logger.info(f"主动调度器启动: 群聊间隔{group_interval//60}分钟, 私聊间隔{private_interval//60}分钟")
    
    def stop(self):
        self.scheduler.shutdown()
    
    def record_message_time(self, chat_id: str, chat_type: ChatType, is_bot_message: bool = False):
        if not is_bot_message:
            if chat_type == "group":
                self.group_last_msg[chat_id] = datetime.now()
            else:
                self.private_last_msg[chat_id] = datetime.now()
    
    def register_origin(self, chat_id: str, chat_type: ChatType, origin):
        if chat_type == "group":
            self.group_origins[chat_id] = origin
        else:
            self.private_origins[chat_id] = origin
