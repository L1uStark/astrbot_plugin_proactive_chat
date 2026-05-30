# 怕寂寞的AstrBot (Proactive Chat)

让机器人像真正的群友一样，在群聊或私聊中**主动打破沉默**。支持沉默触发、多阶段概率、自我学习、群私分离、自定义人格与独立 LLM。

## ✨ 主要功能

- **沉默触发**：每次有人发言后进入静默等待，只有群聊/私聊彻底沉默一段时间后，机器人才可能主动发言。
- **多阶段概率**：第一、第二阶段分别可设不同的触发概率，第二阶段概率更大，超时强制发言。
- **自我学习**（仅白名单群）：每天凌晨自动分析过去24小时的聊天记录，动态调整沉默时间、窗口时长和概率，并收集群友的说话风格作为参考。
- **学习状态可视化**：在 WebUI 设置页面可查看最近一次学习结果（动态参数、风格例句）。
- **自定义人格**：在配置中直接填写人格描述（如“傲娇猫娘”），机器人会始终遵循该人格。
- **独立 LLM 支持**：可填写自己的 API Key 调用第三方模型；若留空则自动使用 AstrBot 系统默认 LLM。
- **话题权重与类型**：支持历史消息、知识/时间、预设话题、自定义话题四种来源，且权重可按比例自适应。
- **群聊/私聊完全分离**：各自独立的开关、时间窗口、白名单、概率等。

## 📦 安装

1. 将插件文件夹放入 `AstrBot/data/plugins/` 下，确保目录名为 `proactive_chat`。
2. 安装依赖（通常 AstrBot 会自动处理）：
   ```bash
   pip install apscheduler openai anthropic
   ```
3. 重启 AstrBot，或进入 WebUI 插件管理页面启用 proactive_chat。

## 🧠 学习机制详解

· 触发时机：每天凌晨 03:00 自动执行一次学习。
· 学习范围：仅分析 group_allowed_ids 白名单中的群（若白名单为空则不学习）。
· 学习内容：
  · 分析过去 24 小时非机器人消息的沉默间隔，计算平均间隔，据此动态调整 silence_wait、phase1_duration、phase1_prob 等参数。
  · 收集群友在打破沉默时发送的第一条消息作为“风格例句”（最多 20 条）。
· 如何使用学习结果：
  · 动态参数会覆盖你在 WebUI 中设置的静态值，让机器人的发言频率更贴合群的活跃度。
  · 生成主动消息时，随机抽取 3 条风格例句作为语气参考，并强调“保持人设，形成有自己特色的发言”，避免机械模仿。
· 可视化：学习完成后，learning_status 文本框中会显示当前动态参数和最近 5 条风格例句。

## ⚠️ 注意事项

· 时间段与白名单：即使机器人学会了新参数，仍然遵守 start_time ~ end_time 和 allowed_ids 的限制。
· 自己的发言会打断沉默：机器人主动发言后，沉默计时会重置，不会连续发送消息。
· 检查频率：内部循环每分钟检查一次，掷骰机会每 8 分钟一次（可调）。
· 平台支持：依赖 AstrBot 的 send_message、get_chat_history 等接口，目前测试通过 OneBot v11 (QQ)、Telegram 等平台。
· 日志：建议开启 debug_log 并在 AstrBot 全局日志中查看插件运行详情。

## 🧪 测试建议

1. 设置较短的 silence_wait (如 2 分钟) 和较高的 phase1_prob (0.9) 快速验证触发逻辑。
2. 在 group_allowed_ids 中填入一个测试群，发送几条消息后停止发言，观察机器人是否在静默后主动说话。
3. 关闭 group_enabled 并开启 private_enabled，用私聊测试私聊触发。
4. 查看 learning_status 文本框，确认每日学习是否正常运行（需等待凌晨 3 点后）。

## 🐛 常见问题

Q：为什么机器人没有主动发言？
A：请检查是否满足所有条件：总开关、群/私聊开关、时间窗口、白名单、静默等待时间。可在 WebUI 开启 debug_log 并查看日志。

Q：学习功能不工作？
A：确保 group_enabled 已开启，且 group_allowed_ids 不为空（否则学习会自动跳过）。另外确认 AstrBot 的 get_chat_history 接口可用。

Q：我想完全使用系统默认 LLM，怎么设置？
A：将 llm_provider 和 llm_api_key 留空，插件会自动调用 AstrBot 配置好的 LLM。

## 📜 版本

· v1.2.0：新增沉默触发、多阶段概率、自我学习、学习状态可视化、权重自适应
· v1.0.0：初始主动发言功能

作者：L1uStark

## 🚀 部署

将此 `README.md` 放入 `proactive_chat/` 目录，然后同步到容器即可。
```bash
docker cp ~/astrbot/data/plugins/proactive_chat/README.md astrbot:/AstrBot/data/plugins/proactive_chat/
```
