from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import sp
from astrbot.api.message_components import At
from typing import Optional
from astrbot.core import logger


@register(
    "astrbot_group_ban",
    "Tsukumi233",
    "群聊黑名单插件，用于禁用指定群聊使用机器人功能的插件，ban-help获取帮助",
    "2.0.0",
)
class BanPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        
        # 从插件配置中获取是否启用禁用功能，默认为启用
        self.enable = config.get('enable', True)
        # 从配置文件获取初始黑名单
        config_banned_groups = config.get('banned_groups', [])
        # 持久化存储，使用 sp 接口加载数据（数据存储为 list，转换为 set 便于处理）
        sp_banned_groups = sp.get('ban_plugin_banned_groups', [])
        # 合并配置文件和持久化存储的黑名单
        self.banned_groups = set(config_banned_groups + sp_banned_groups)

    def persist(self):
        """将当前禁用数据持久化保存"""
        sp.put('ban_plugin_banned_groups', list(self.banned_groups))
        sp.put('ban_plugin_enable', self.enable)

    def is_group_banned(self, event: AstrMessageEvent):
        """判断群聊是否被禁用。对于群聊场景：
           检查是否在黑名单中。私聊消息不受影响。"""
        group_id = event.message_obj.group_id if hasattr(event.message_obj, "group_id") else None
        
        # 私聊消息不受群聊黑名单影响
        if not group_id:
            return False
            
        # 如果在黑名单中，禁用使用
        if group_id in self.banned_groups:
            logger.info(f"群聊 {group_id} 被禁用")
            return True
            
        return False

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE, priority=999)
    async def filter_banned_groups(self, event: AstrMessageEvent):
        """
        全局群聊事件过滤器：
        如果禁用功能启用且群聊被禁用，则停止事件传播，机器人不再响应该群的消息。
        使用最高优先级确保在其他插件之前执行。
        
        注意：对于参数不足的指令（如 /wc），可能会先显示错误信息再终止事件传播。
        这是因为AstrBot的异常处理机制会在事件终止之前发送错误信息。
        """
        if not self.enable:
            return
        if self.is_group_banned(event):
            logger.info(f"群聊 {event.message_obj.group_id} 被禁用，停止事件传播")
            event.stop_event()
            return

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("ban")
    async def ban_group(self, event: AstrMessageEvent, group_id: Optional[str] = None):
        """
        禁用指定群聊使用机器人的权限。
        格式：/ban <群号> 或 /ban（禁用当前群聊）
        支持指定群号或禁用当前群聊。
        """
        target_group_id: str
        if group_id:
            target_group_id = group_id
        else:
            # 如果没有指定群号，使用当前群聊
            current_group_id = event.message_obj.group_id if hasattr(event.message_obj, "group_id") else None
            if not current_group_id:
                yield event.plain_result("请在 /ban 后指定群号，或在群聊中使用 /ban 禁用当前群聊。")
                return
            target_group_id = str(current_group_id)

        # 添加到黑名单
        self.banned_groups.add(target_group_id)
        self.persist()
        yield event.plain_result(f"已禁用群聊 {target_group_id} 使用机器人的权限。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("pass")
    async def allow_group(self, event: AstrMessageEvent, group_id: Optional[str] = None):
        """
        允许指定群聊使用机器人功能。
        格式：/pass <群号> 或 /pass（允许当前群聊）
        支持指定群号或允许当前群聊。
        """
        target_group_id: str
        if group_id:
            target_group_id = group_id
        else:
            # 如果没有指定群号，使用当前群聊
            current_group_id = event.message_obj.group_id if hasattr(event.message_obj, "group_id") else None
            if not current_group_id:
                yield event.plain_result("请在 /pass 后指定群号，或在群聊中使用 /pass 允许当前群聊。")
                return
            target_group_id = str(current_group_id)

        # 从黑名单中移除
        self.banned_groups.discard(target_group_id)
        self.persist()
        yield event.plain_result(f"已允许群聊 {target_group_id} 使用机器人功能。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("pass-all")
    async def allow_all_groups(self, event: AstrMessageEvent):
        """
        允许所有群聊使用机器人功能。
        格式：/pass-all
        执行后，所有群聊都将可以使用机器人功能。
        """
        # 清空黑名单，恢复默认状态
        self.banned_groups.clear()
        self.persist()
        yield event.plain_result("已允许所有群聊使用机器人功能。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("ban_enable")
    async def ban_enable(self, event: AstrMessageEvent):
        """
        启用禁用功能。
        格式：/ban_enable
        """
        self.enable = True
        self.persist()
        yield event.plain_result("已临时启用禁用功能，重启后失效。永久启用请在插件配置中修改。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("ban_disable")
    async def ban_disable(self, event: AstrMessageEvent):
        """
        禁用禁用功能。
        格式：/ban_disable
        """
        self.enable = False
        self.persist()
        yield event.plain_result("已禁用禁用功能，重启后失效。永久禁用请在插件配置中修改。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("banlist")
    async def list_banned_groups(self, event: AstrMessageEvent):
        """
        列出当前被禁用的群聊。
        格式：/banlist
        """
        if self.banned_groups:
            yield event.plain_result(f"被禁用的群聊: {', '.join(self.banned_groups)}")
        else:
            yield event.plain_result("被禁用的群聊: 无")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("ban-help")
    async def ban_help(self, event: AstrMessageEvent):
        """
        管理员专用命令：显示该插件所有命令列表及功能说明。
        格式：/ban-help
        """
        help_text = (
            "【群聊黑名单插件命令帮助】\n"
            "1. /ban <群号>：禁用指定群聊使用机器人功能\n"
            "2. /ban：禁用当前群聊使用机器人功能\n"
            "3. /pass <群号>：允许指定群聊使用机器人功能\n"
            "4. /pass：允许当前群聊使用机器人功能\n"
            "5. /pass-all：允许所有群聊使用机器人功能\n"
            "6. /ban_enable：启用禁用功能\n"
            "7. /ban_disable：禁用禁用功能\n"
            "8. /banlist：列出当前被禁用的群聊\n"
            "9. /ban-help：显示此帮助信息\n\n"
            "注意：私聊消息不受群聊黑名单影响。\n"
            "注意：对于参数不足的指令，可能会先显示错误信息再终止事件传播。"
        )
        yield event.plain_result(help_text)
