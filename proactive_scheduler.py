import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Literal
from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain

from .utils import time_str_to_minutes
from .topic_manager import TopicManager
from .llm_client import LLMClient
from .learner import SilenceLearner

ChatType = Literal["group", "private"]

class SessionState:
    def __init__(self):
        self.last_message_time = None
        self.phase = "waiting"
        self.phase_start = None
        self.origin = None
        self.last_dice_time = None
        self.consecutive_speaks = 0

class ProactiveScheduler:
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.context = plugin_instance.context
        self.config = plugin_instance.config

        self.group_sessions: Dict[str, SessionState] = {}
        self.private_sessions: Dict[str, SessionState] = {}

        self.topic_manager = TopicManager(plugin_instance)
        self.learner = SilenceLearner(plugin_instance)
        self._llm_client = None
        self._running = False
        self._task = None
        self._learn_task = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        self._learn_task = asyncio.create_task(self._daily_learn_scheduler())
        logger.info("[日志] 沉默触发调度器已启动，每日学习已安排（等待消息触发）")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        if self._learn_task:
            self._learn_task.cancel()
        logger.info("[日志] 沉默触发调度器已停止")

    async def _daily_learn_scheduler(self):
        while self._running:
            now = datetime.now()
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if target < now:
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            await asyncio.sleep(wait)
            try:
                await self.learner.daily_learn("group")
            except Exception as e:
                logger.error(f"学习任务失败: {e}")

    def register_origin(self, chat_id: str, chat_type: ChatType, origin):
        sessions = self.group_sessions if chat_type == "group" else self.private_sessions
        if chat_id not in sessions:
            sessions[chat_id] = SessionState()
        sessions[chat_id].origin = origin
        logger.info(f"[日志] 注册 {chat_type} {chat_id} 的 origin")

    def on_message_received(self, chat_id: str, chat_type: ChatType):
        sessions = self.group_sessions if chat_type == "group" else self.private_sessions
        if chat_id not in sessions:
            sessions[chat_id] = SessionState()
        state = sessions[chat_id]
        state.last_message_time = datetime.now()
        state.phase = "waiting"
        state.phase_start = None
        state.last_dice_time = None
        state.consecutive_speaks = 0
        logger.info(f"[日志] {chat_type} {chat_id} 收到消息，重置为静默等待（计数器已清零）")

    async def _loop(self):
        logger.info("[日志] 调度循环已启动")
        while self._running:
            try:
                await asyncio.sleep(60)
                if not self.config.get("enabled", True):
                    continue
                logger.info("[日志] 开始检查会话...")
                await self._check_all("group")
                await self._check_all("private")
            except Exception as e:
                logger.error(f"调度循环出错: {e}", exc_info=True)

    def _is_in_time_window(self, start_str: str, end_str: str) -> bool:
        """判断当前时间是否在允许的时间窗口内，支持跨日"""
        now = datetime.now()
        start_min = time_str_to_minutes(start_str)
        end_min = time_str_to_minutes(end_str)
        now_min = now.hour * 60 + now.minute

        if start_min <= end_min:
            # 不跨日：08:00 - 23:00
            return start_min <= now_min <= end_min
        else:
            # 跨日：22:00 - 02:00
            return now_min >= start_min or now_min <= end_min

    async def _check_all(self, chat_type: ChatType):
        if not self.config.get(f"{chat_type}_enabled", True):
            logger.info(f"[日志] {chat_type} 总开关未开启")
            return

        # 时间窗口判断
        start_key = f"{chat_type}_start_time"
        end_key = f"{chat_type}_end_time"
        if not self._is_in_time_window(
            self.config.get(start_key, "00:00"),
            self.config.get(end_key, "23:59")
        ):
            logger.info(f"[日志] {chat_type} 不在允许时间段内")
            return

        allowed_ids = self.config.get(f"{chat_type}_allowed_ids", [])
        sessions = self.group_sessions if chat_type == "group" else self.private_sessions

        logger.info(f"[日志] {chat_type} 触发检查: 当前活跃会话数={len(sessions)}")
        for chat_id, state in list(sessions.items()):
            if allowed_ids and chat_id not in allowed_ids:
                logger.info(f"[日志] {chat_type} {chat_id} 不在白名单，跳过")
                continue
            if not state.origin:
                logger.info(f"[日志] {chat_type} {chat_id} 缺少 origin，跳过")
                continue
            await self._process_session(chat_id, chat_type, state, datetime.now())

    async def _process_session(self, chat_id: str, chat_type: ChatType, state: SessionState, now: datetime):
        max_consecutive = self.config.get(f"{chat_type}_max_consecutive_speaks", 1)
        if max_consecutive > 0 and state.consecutive_speaks >= max_consecutive:
            logger.info(f"[日志] {chat_type} {chat_id} 连续发言已达上限，暂停计时")
            return

        wait = self.learner.get_dynamic_param("silence_wait", self.config.get(f"{chat_type}_silence_wait", 10))
        dur1 = self.learner.get_dynamic_param("phase1_duration", self.config.get(f"{chat_type}_phase1_duration", 40))
        prob1 = self.learner.get_dynamic_param("phase1_prob", self.config.get(f"{chat_type}_phase1_prob", 0.15))
        dur2 = self.learner.get_dynamic_param("phase2_duration", self.config.get(f"{chat_type}_phase2_duration", 60))
        prob2 = self.learner.get_dynamic_param("phase2_prob", self.config.get(f"{chat_type}_phase2_prob", 0.6))
        check_interval = self.config.get(f"{chat_type}_check_interval", 8)

        if state.last_message_time is None:
            state.last_message_time = now
            return

        silent_minutes = (now - state.last_message_time).total_seconds() / 60
        logger.info(f"[日志] {chat_type} {chat_id} 已沉默 {silent_minutes:.1f} 分钟，当前阶段: {state.phase}, 连续发言: {state.consecutive_speaks}/{max_consecutive}")

        if state.phase == "waiting":
            if silent_minutes >= wait:
                state.phase = "phase1"
                state.phase_start = now
                state.last_dice_time = None
                logger.info(f"[日志] {chat_type} {chat_id} 进入第一阶段（wait={wait}min）")
            return

        should_dice = False
        if state.last_dice_time is None:
            should_dice = True
        else:
            since_last_dice = (now - state.last_dice_time).total_seconds() / 60
            if since_last_dice >= check_interval:
                should_dice = True

        if not should_dice:
            return

        state.last_dice_time = now

        if state.phase == "phase1":
            elapsed1 = (now - state.phase_start).total_seconds() / 60 if state.phase_start else 0
            if elapsed1 >= dur1:
                state.phase = "phase2"
                state.phase_start = now
                state.last_dice_time = None
                logger.info(f"[日志] {chat_type} {chat_id} 进入第二阶段")
                return
            dice = random.random()
            logger.info(f"[日志] {chat_type} {chat_id} 第一阶段掷骰: {dice:.3f} (阈值: {prob1})")
            if dice < prob1:
                logger.info(f"[日志] {chat_type} {chat_id} 第一阶段掷骰成功，准备发言")
                await self._trigger_speak(chat_id, chat_type, state)
                return

        elif state.phase == "phase2":
            elapsed2 = (now - state.phase_start).total_seconds() / 60 if state.phase_start else 0
            if elapsed2 >= dur2:
                logger.info(f"[日志] {chat_type} {chat_id} 第二阶段超时，强制发言")
                await self._trigger_speak(chat_id, chat_type, state)
                return
            dice = random.random()
            logger.info(f"[日志] {chat_type} {chat_id} 第二阶段掷骰: {dice:.3f} (阈值: {prob2})")
            if dice < prob2:
                logger.info(f"[日志] {chat_type} {chat_id} 第二阶段掷骰成功，准备发言")
                await self._trigger_speak(chat_id, chat_type, state)
                return

    async def _trigger_speak(self, chat_id: str, chat_type: ChatType, state: SessionState):
        await self._send_proactive_message(state.origin, chat_id, chat_type)
        max_consecutive = self.config.get(f"{chat_type}_max_consecutive_speaks", 1)
        state.consecutive_speaks += 1
        logger.info(f"[日志] {chat_type} {chat_id} 连续发言次数: {state.consecutive_speaks}/{max_consecutive}")
        if max_consecutive > 0 and state.consecutive_speaks >= max_consecutive:
            state.last_message_time = None
            state.phase = "waiting"
            state.phase_start = None
            state.last_dice_time = None
            logger.info(f"[日志] {chat_type} {chat_id} 已达连续发言上限，暂停计时，等待新消息")
        else:
            self.on_message_received(chat_id, chat_type)

    def _get_personality_text(self) -> str:
        custom = self.config.get("personality_custom", "").strip()
        if custom:
            return custom
        try:
            personality = self.context.get_personality()
            if personality and personality.description:
                return personality.description
        except Exception:
            pass
        return "一个友好的聊天机器人"

    def _get_llm_client(self):
        if self._llm_client is None:
            llm_provider = self.config.get("llm_provider", "")
            llm_api_key = self.config.get("llm_api_key", "")
            if not llm_provider or not llm_api_key:
                return None
            personality_text = self._get_personality_text()
            try:
                self._llm_client = LLMClient(self.config, personality_text)
            except Exception as e:
                logger.error(f"LLM客户端创建失败: {e}")
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
                    f"要求：自然、简短（不超过50字），不要加引号。"
                )
                response = await llm_tools.text_chat(prompt)
                if response:
                    return response.strip()
        except Exception as e:
            logger.error(f"系统LLM生成失败: {e}")
        return None

    async def _send_proactive_message(self, origin, chat_id: str, chat_type: ChatType):
        logger.info(f"[日志] 准备为 {chat_type} {chat_id} 生成主动消息")
        weights = {
            "history": self.config.get("weight_history", 30),
            "knowledge": self.config.get("weight_knowledge", 25),
            "preset": self.config.get("weight_preset", 20),
            "custom": self.config.get("weight_custom", 25)
        }
        total = sum(weights.values())
        if total == 0:
            weights = {k: 25 for k in weights}
        items = list(weights.keys())
        probs = [weights[k] / total for k in items]
        source = random.choices(items, weights=probs, k=1)[0]

        logger.info(f"话题来源: {source}")

        message = None

        if source == "preset":
            message = self.topic_manager.get_preset_topic(chat_type)
        else:
            topic_prompt = None
            if source == "custom":
                topic_prompt = self.topic_manager.get_custom_topic()
                if not topic_prompt:
                    message = self.topic_manager.get_preset_topic(chat_type)
            elif source == "knowledge":
                topic_prompt = self.topic_manager.get_knowledge_topic(chat_type)
            elif source == "history":
                topic_prompt = self.topic_manager.get_history_topic(chat_type, chat_id)
                if not topic_prompt:
                    message = self.topic_manager.get_preset_topic(chat_type)

            if topic_prompt and message is None:
                llm_client = self._get_llm_client()
                try:
                    if llm_client:
                        message = await llm_client.generate_response(topic_prompt, chat_type)
                    else:
                        message = await self._generate_message_with_system_llm(topic_prompt, chat_type)
                    if not isinstance(message, str) or not message.strip():
                        message = self.topic_manager.get_preset_topic(chat_type)
                except Exception as e:
                    logger.error(f"LLM生成失败: {e}，降级预设")
                    message = self.topic_manager.get_preset_topic(chat_type)

        if not isinstance(message, str) or not message.strip():
            message = "今天想聊点什么呢？"
        else:
            message = message.strip()

        await self._send_raw_message(origin, message, chat_id, chat_type)

    async def _send_raw_message(self, origin, message, chat_id: str, chat_type: ChatType):
        if message is None:
            message = ""
        if not isinstance(message, str):
            message = str(message)
        if not message.strip():
            message = "今天想聊点什么呢？"

        logger.info(f"[日志] 最终发送消息: type={type(message).__name__}, len={len(message)}")
        try:
            chain = MessageChain([Plain(text=message)])
            await self.context.send_message(origin, chain)
            logger.info(f"✓ 主动消息已发送 -> {chat_type} {chat_id}: {message[:50]}...")
        except Exception as e:
            logger.error(f"✗ 发送失败: {e}", exc_info=True)
