import asyncio
import random
from datetime import datetime
from typing import Dict, Any, Literal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain

from .utils import time_str_to_minutes
from .topic_manager import TopicManager
from .llm_client import LLMClient

ChatType = Literal["group", "private"]

class ProactiveScheduler:
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.context = plugin_instance.context
        self.config = plugin_instance.plugin_config

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
        custom = self.config.get("personality_custom", "").strip()
        if custom:
            logger.debug("使用自定义人格")
            return custom
        try:
            personality = self.context.get_personality()
            if personality and personality.description:
                logger.debug("使用系统人设")
                return personality.description
        except Exception as e:
            logger.debug(f"获取系统人设失败: {e}")
        logger.debug("使用默认人格")
        return "一个友好的聊天机器人"

    def _get_llm_client(self):
        if self._llm_client is None:
            llm_provider = self.config.get("llm_provider", "")
            llm_api_key = self.config.get("llm_api_key", "")
            if not llm_provider or not llm_api_key:
                logger.info("未配置独立 LLM，将使用系统默认 LLM")
                return None
            personality_text = self._get_personality_text()
            try:
                self._llm_client = LLMClient(self.config, personality_text)
                if self._llm_client.client is None:
                    logger.warning("独立 LLM 客户端初始化失败，将降级使用系统默认 LLM")
                    self._llm_client = None
            except Exception as e:
                logger.error(f"独立 LLM 客户端创建失败: {e}")
                self._llm_client = None
        return self._llm_client

    async def _generate_message_with_system_llm(self, topic_prompt: str, chat_type: ChatType) -> str:
        try:
            llm_tools = self.context.get_llm_tools()
            if llm_tools:
                personality_text = self._get_personality_text()
                audience = "大家" if chat_type == "group" else "你"
                prompt = (
                    f"你的人设：{personality_text}\n"
                    f"根据以下话题提示生成一句主动聊天消息，对象是{audience}。\n"
                    f"话题提示：{topic_prompt}\n"
                    f"要求自然简短不超50字，不要加引号。"
                )
                response = await llm_tools.text_chat(prompt)
                return response.strip()
        except Exception as e:
            logger.error(f"系统 LLM 生成失败: {e}")
        fallback = self.topic_manager.get_preset_topic(chat_type)
        logger.info(f"降级使用预设话题: {fallback}")
        return fallback

    async def _send_proactive_message(self, origin, chat_id: str, chat_type: ChatType):
        logger.info(f"开始为 {chat_type} {chat_id} 生成主动消息")
        
        # ✅ 修改点：从4个独立权重字段拼装字典
        prefix = "group_" if chat_type == "group" else "private_"
        weights = {
            "history": self.config.get(f"{prefix}weight_history", 30),
            "knowledge": self.config.get(f"{prefix}weight_knowledge", 25),
            "preset": self.config.get(f"{prefix}weight_preset", 20),
            "custom": self.config.get(f"{prefix}weight_custom", 25)
        }
        
        source = self.topic_manager.select_source(weights)
        logger.info(f"为 {chat_type} {chat_id} 选择话题来源: {source} (权重分布: {weights})")
        
        topic_prompt = None
        if source == "preset":
            message = self.topic_manager.get_preset_topic(chat_type)
            logger.info(f"使用预设话题直接发言: {message}")
            await self._send_raw_message(origin, message, chat_id, chat_type)
            return
        
        elif source == "custom":
            topic_prompt = self.topic_manager.get_custom_topic()
            if not topic_prompt:
                logger.warning("自定义主题列表为空，降级到预设话题")
                message = self.topic_manager.get_preset_topic(chat_type)
                await self._send_raw_message(origin, message, chat_id, chat_type)
                return
            logger.info(f"自定义主题: {topic_prompt}")
        
        elif source == "knowledge":
            topic_prompt = self.topic_manager.get_knowledge_topic(chat_type)
            logger.info(f"知识话题: {topic_prompt}")
        
        elif source == "history":
            topic_prompt = self.topic_manager.get_history_topic(chat_type, chat_id)
            if not topic_prompt:
                logger.warning("获取历史话题失败，降级到预设话题")
                message = self.topic_manager.get_preset_topic(chat_type)
                await self._send_raw_message(origin, message, chat_id, chat_type)
                return
            logger.info(f"历史话题: {topic_prompt}")
        
        if topic_prompt:
            llm_client = self._get_llm_client()
            try:
                if llm_client:
                    message = await llm_client.generate_response(topic_prompt, chat_type)
                else:
                    message = await self._generate_message_with_system_llm(topic_prompt, chat_type)
                await self._send_raw_message(origin, message, chat_id, chat_type)
            except Exception as e:
                logger.error(f"LLM 生成消息失败: {e}，降级使用预设话题")
                message = self.topic_manager.get_preset_topic(chat_type)
                await self._send_raw_message(origin, message, chat_id, chat_type)
        else:
            logger.error("未获取到任何话题提示，使用默认预设话题")
            message = self.topic_manager.get_preset_topic(chat_type)
            await self._send_raw_message(origin, message, chat_id, chat_type)

    async def _send_raw_message(self, origin, message: str, chat_id: str, chat_type: ChatType):
        try:
            message_chain = MessageChain().message(Plain(text=message))
            await self.context.send_message(origin, message_chain)
            if chat_type == "group":
                self.group_last_chat[chat_id] = datetime.now()
            else:
                self.private_last_chat[chat_id] = datetime.now()
            logger.info(f"✓ 主动消息发送成功 -> {chat_type} {chat_id}: {message[:50]}...")
        except Exception as e:
            logger.error(f"✗ 发送主动消息失败 -> {chat_type} {chat_id}: {type(e).__name__}: {str(e)}")

    async def _check_and_trigger_for_type(self, chat_type: ChatType):
        enabled_key = f"{chat_type}_enabled"
        if not self.config.get(enabled_key, True):
            logger.debug(f"{chat_type} 主动聊天总开关未开启，跳过")
            return
        
        now = datetime.now()
        start_key = f"{chat_type}_start_time"
        end_key = f"{chat_type}_end_time"
        start_min = time_str_to_minutes(self.config.get(start_key, "00:00"))
        end_min = time_str_to_minutes(self.config.get(end_key, "23:59"))
        now_min = now.hour * 60 + now.minute
        if not (start_min <= now_min <= end_min):
            logger.debug(f"{chat_type} 不在允许时间段内 ({start_key}~{end_key})，跳过")
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
        
        logger.debug(f"{chat_type} 触发检查: 当前活跃会话数={len(origins_dict)}")
        
        for chat_id, origin in list(origins_dict.items()):
            if allowed_ids and chat_id not in allowed_ids:
                logger.debug(f"{chat_type} {chat_id} 不在白名单，跳过")
                continue
            
            if random.random() > prob:
                logger.debug(f"{chat_type} {chat_id} 触发概率未命中 (prob={prob})，跳过")
                continue
            
            last_chat = last_chat_dict.get(chat_id)
            if last_chat:
                minutes_since_chat = (now - last_chat).total_seconds() / 60
                if minutes_since_chat < min_interval:
                    logger.debug(f"{chat_type} {chat_id} 距离上次主动聊天仅 {minutes_since_chat:.1f} 分钟 < {min_interval}，跳过")
                    continue
            
            last_msg = last_msg_dict.get(chat_id)
            if last_msg:
                minutes_since_msg = (now - last_msg).total_seconds() / 60
                if minutes_since_msg < isolation:
                    logger.debug(f"{chat_type} {chat_id} 最后一条消息距今 {minutes_since_msg:.1f} 分钟 < {isolation}，隔离期内跳过")
                    continue
            
            logger.info(f"{chat_type} {chat_id} 满足所有触发条件，准备发送主动消息")
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
        logger.info(f"主动调度器启动: 群聊间隔 {group_interval//60} 分钟, 私聊间隔 {private_interval//60} 分钟")
    
    def stop(self):
        self.scheduler.shutdown()
        logger.info("主动调度器已停止")
    
    def record_message_time(self, chat_id: str, chat_type: ChatType, is_bot_message: bool = False):
        if not is_bot_message:
            if chat_type == "group":
                self.group_last_msg[chat_id] = datetime.now()
                logger.debug(f"记录群聊 {chat_id} 最后消息时间")
            else:
                self.private_last_msg[chat_id] = datetime.now()
                logger.debug(f"记录私聊 {chat_id} 最后消息时间")
    
    def register_origin(self, chat_id: str, chat_type: ChatType, origin):
        if chat_type == "group":
            self.group_origins[chat_id] = origin
            logger.debug(f"注册群聊 {chat_id} 的 origin")
        else:
            self.private_origins[chat_id] = origin
            logger.debug(f"注册私聊 {chat_id} 的 origin")
