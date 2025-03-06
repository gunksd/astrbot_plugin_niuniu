import random
import time
import yaml
from astrbot.api.all import AstrMessageEvent

class NiuniuGames:
    def __init__(self, main_plugin):
        self.main = main_plugin  # 主插件实例

    async def start_rush(self, event: AstrMessageEvent):
        """冲(咖啡)游戏"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        # 检查插件是否启用
        if not self.main.get_group_data(group_id).get('plugin_enabled', False):
            yield event.plain_result("❌ 插件未启用")
            return

        # 获取用户数据
        user_data = self.main.get_user_data(group_id, user_id)
        if not user_data:
            yield event.plain_result("❌ 请先注册牛牛")
            return

        # 检查是否已经在冲
        if user_data.get('is_rushing', False):
            remaining_time = user_data['rush_start_time'] + 1800 - time.time()
            if remaining_time > 0:
                mins = int(remaining_time // 60) + 1
                yield event.plain_result(f"⏳ {nickname} 你已经在冲了")
                return

        # 开始
        user_data['is_rushing'] = True
        user_data['rush_start_time'] = time.time()
        self.main._save_niuniu_lengths()

        yield event.plain_result(f"💪 {nickname} 芜湖！开冲！你暂时无法主动打胶或者比划！输入\"停止开冲\"来结束并结算金币。")

    async def stop_rush(self, event: AstrMessageEvent):
        """停止开冲并结算金币"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        # 获取用户数据
        user_data = self.main.get_user_data(group_id, user_id)
        if not user_data:
            yield event.plain_result("❌ 请先注册牛牛")
            return

        # 检查是否在冲
        if not user_data.get('is_rushing', False):
            yield event.plain_result(f"❌ {nickname} 你当前没有在冲")
            return

        # 计算时间
        work_time = time.time() - user_data['rush_start_time']

        # 如果时间少于10分钟，没有奖励
        if work_time < 600:  # 10分钟 = 600秒
            yield event.plain_result(f"❌ {nickname} 没有冲够10分钟，没有奖励！")
            return

        # 如果时间超过30分钟，按30分钟计算
        work_time = min(work_time, 1800)  # 30分钟 = 1800秒

        # 动态计算金币奖励
        coins_per_minute = random.randint(1, 2)
        coins = int((work_time / 60) * coins_per_minute)

        # 更新用户金币
        user_data['coins'] = user_data.get('coins', 0) + coins
        self.main._save_niuniu_lengths()

        yield event.plain_result(f"🎉 {nickname} 总算冲够了！你获得了 {coins} 金币！")

        # 重置状态
        user_data['is_rushing'] = False
        self.main._save_niuniu_lengths()

    async def fly_plane(self, event: AstrMessageEvent):
        """飞机游戏"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()

        # 检查插件是否启用
        if not self.main.get_group_data(group_id).get('plugin_enabled', False):
            yield event.plain_result("❌ 插件未启用")
            return

        # 获取用户数据
        user_data = self.main.get_user_data(group_id, user_id)
        if not user_data:
            yield event.plain_result("❌ 请先注册牛牛")
            return

        # 检查冷却时间
        last_fly_time = user_data.get('last_fly_time', 0)
        current_time = time.time()
        if current_time - last_fly_time < 14400:  # 4小时
            remaining_time = 14400 - (current_time - last_fly_time)
            mins = int(remaining_time // 60) + 1
            yield event.plain_result(f"✈️ 油箱空了，{nickname} {mins}分钟后可再起飞")
            return

        # 定义不同的飞行事件
        fly_events = [
            {"description": "短途路线", "coins": random.randint(50, 70)},
            {"description": "国际航班", "coins": random.randint(80, 100)},
            {"description": "平安抵达", "coins": random.randint(60, 80)},
            {"description": "遇到冷空气", "coins": random.randint(40, 60)},
            {"description": "顺利抵达", "coins": random.randint(70, 90)}
        ]

        # 随机选择一个事件
        event_data = random.choice(fly_events)
        description = event_data["description"]
        coins = event_data["coins"]

        # 更新用户金币
        user_data['coins'] = user_data.get('coins', 0) + coins
        user_data['last_fly_time'] = current_time
        self.main._save_niuniu_lengths()

        yield event.plain_result(f"🎉 {nickname} {description}！你获得了 {coins} 金币！")

    def update_user_coins(self, group_id: str, user_id: str, coins: float):
        """更新用户金币"""
        user_data = self.main.get_user_data(group_id, user_id)
        if user_data:
            user_data['coins'] = user_data.get('coins', 0) + coins
            self.main._save_niuniu_lengths()

    def get_user_coins(self, group_id: str, user_id: str) -> float:
        """获取用户金币"""
        user_data = self.main.get_user_data(group_id, user_id)
        return user_data.get('coins', 0) if user_data else 0
