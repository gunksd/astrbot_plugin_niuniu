import random
import yaml
import os
import re
import time
from astrbot.api.all import *

# 常量定义
PLUGIN_DIR = os.path.join('data', 'plugins', 'astrbot_plugin_niuniu')
os.makedirs(PLUGIN_DIR, exist_ok=True)
NIUNIU_LENGTHS_FILE = os.path.join('data', 'niuniu_lengths.yml')
NIUNIU_TEXTS_FILE = os.path.join(PLUGIN_DIR, 'niuniu_game_texts.yml')

@register("niuniu_plugin", "长安某", "牛牛插件，包含注册牛牛、打胶、我的牛牛、比划比划、牛牛排行等功能", "3.1.1")
class NiuniuPlugin(Star):
    # 冷却时间常量（秒）
    COOLDOWN_10_MIN = 600    # 10分钟
    COOLDOWN_30_MIN = 1800   # 30分钟
    COMPARE_COOLDOWN = 600   # 比划冷却
    INVITE_LIMIT = 3         # 邀请次数限制

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.niuniu_lengths = self._load_niuniu_lengths()
        self.niuniu_texts = self._load_niuniu_texts()
        self.last_dajiao_time = {}      # {str(group_id): {str(user_id): last_time}}
        self.invite_count = {}          # {str(group_id): {str(user_id): (last_time, count)}}
        self.last_compare_time = {}     # {str(group_id): {str(user_id): {str(target_id): last_time}}}

    # region 数据管理
    def _create_niuniu_lengths_file(self):
        """创建数据文件"""
        try:
            with open(NIUNIU_LENGTHS_FILE, 'w', encoding='utf-8') as f:
                yaml.dump({}, f)
        except Exception as e:
            self.context.logger.error(f"创建文件失败: {str(e)}")

    def _load_niuniu_lengths(self):
        """加载牛牛数据"""
        if not os.path.exists(NIUNIU_LENGTHS_FILE):
            self._create_niuniu_lengths_file()
        
        try:
            with open(NIUNIU_LENGTHS_FILE, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            # 数据结构验证
            for group_id in list(data.keys()):
                group_data = data[group_id]
                if not isinstance(group_data, dict):
                    data[group_id] = {'plugin_enabled': True}
                elif 'plugin_enabled' not in group_data:
                    group_data['plugin_enabled'] = True
            return data
        except Exception as e:
            self.context.logger.error(f"加载数据失败: {str(e)}")
            return {}

    def _load_niuniu_texts(self):
        """加载游戏文本"""
        default_texts = {
            'register': {
                'success': "🧧 {nickname} 成功注册牛牛！\n📏 初始长度：{length}cm\n💪 硬度等级：{hardness}",
                'already_registered': "⚠️ {nickname} 你已经注册过牛牛啦！",
                'only_group': "❌ 请在群聊中注册牛牛"
            },
            'dajiao': {
                'cooldown': [
                    "⏳ {nickname} 牛牛需要休息，{remaining}分钟后可再打胶",
                    "🛑 冷却中，{nickname} 请耐心等待 (＞﹏＜)"
                ],
                'increase': [
                    "🚀 {nickname} 打胶成功！长度增加 {change}cm！",
                    "🎉 {nickname} 的牛牛茁壮成长！+{change}cm"
                ],
                'decrease': [
                    "😱 {nickname} 用力过猛！长度减少 {change}cm！",
                    "⚠️ {nickname} 操作失误！-{change}cm"
                ],
                'no_effect': [
                    "🌀 {nickname} 的牛牛毫无变化...",
                    "🔄 {nickname} 这次打胶没有效果"
                ],
                'not_registered': "❌ {nickname} 请先注册牛牛"
            },
            'my_niuniu': {
                'info': "📊 {nickname} 的牛牛状态\n📏 长度：{length}\n💪 硬度：{hardness}\n📝 评价：{evaluation}",
                'evaluation': {
                    'short': ["小巧玲珑", "精致可爱"],
                    'medium': ["中规中矩", "潜力无限"],
                    'long': ["威风凛凛", "傲视群雄"],
                    'very_long': ["擎天巨柱", "突破天际"]
                },
                'not_registered': "❌ {nickname} 请先注册牛牛"
            },
            'compare': {
                'no_target': "❌ {nickname} 请指定比划对象",
                'target_not_registered': "❌ 对方尚未注册牛牛",
                'cooldown': "⏳ {nickname} 请等待{remaining}分钟后再比划",
                'limit': "🛑 {nickname} 今日比划次数已达上限",
                'self_compare': "❌ 不能和自己比划",
                'win': [
                    "🎉 {winner} 战胜了 {loser}！\n📈 增加 {gain}cm",
                    "🏆 {winner} 的牛牛更胜一筹！+{gain}cm"
                ],
                'lose': [
                    "😭 {loser} 败给 {winner}\n📉 减少 {loss}cm",
                    "💔 {loser} 的牛牛不敌对方！-{loss}cm"
                ],
                'draw': "🤝 双方势均力敌！"
            },
            'ranking': {
                'header': "🏅 牛牛排行榜 TOP10：\n",
                'no_data': "📭 本群暂无牛牛数据",
                'item': "{rank}. {name} ➜ {length}"
            },
            'menu': {
                'default': """📜 牛牛菜单：
🔹 注册牛牛 - 初始化你的牛牛
🔹 打胶 - 提升牛牛长度
🔹 我的牛牛 - 查看当前状态
🔹 比划比划 @目标 - 发起对决
🔹 牛牛排行 - 查看群排行榜
🔹 牛牛开/关 - 管理插件"""
            },
            'system': {
                'enable': "✅ 牛牛插件已启用",
                'disable': "❌ 牛牛插件已禁用"
            }
        }
        
        try:
            if os.path.exists(NIUNIU_TEXTS_FILE):
                with open(NIUNIU_TEXTS_FILE, 'r', encoding='utf-8') as f:
                    custom_texts = yaml.safe_load(f) or {}
                    return self._deep_merge(default_texts, custom_texts)
        except Exception as e:
            self.context.logger.error(f"加载文本失败: {str(e)}")
        return default_texts

    def _deep_merge(self, base, update):
        """深度合并字典"""
        for key, value in update.items():
            if isinstance(value, dict):
                base[key] = self._deep_merge(base.get(key, {}), value)
            else:
                base[key] = value
        return base

    def _save_niuniu_lengths(self):
        """保存数据"""
        try:
            with open(NIUNIU_LENGTHS_FILE, 'w', encoding='utf-8') as f:
                yaml.dump(self.niuniu_lengths, f, allow_unicode=True)
        except Exception as e:
            self.context.logger.error(f"保存失败: {str(e)}")
    # endregion

    # region 工具方法
    def format_length(self, length):
        """格式化长度显示"""
        if length >= 100:
            return f"{length/100:.2f}m"
        return f"{length}cm"

    def get_group_data(self, group_id):
        """获取群组数据"""
        group_id = str(group_id)
        if (group_id) not in self.niuniu_lengths:
            self.niuniu_lengths[group_id] = {'plugin_enabled': True}
        return self.niuniu_lengths[group_id]

    def get_user_data(self, group_id, user_id):
        """获取用户数据"""
        group_data = self.get_group_data(group_id)
        user_id = str(user_id)
        return group_data.get(user_id)

    def check_cooldown(self, last_time, cooldown):
        """检查冷却时间"""
        current = time.time()
        elapsed = current - last_time
        remaining = cooldown - elapsed
        return remaining > 0, remaining

    def parse_at_target(self, event):
        """解析@目标"""
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                return str(comp.qq)
        return None

    def parse_target(self, event):
        """解析@目标或用户名"""
        for comp in event.message_obj.message:
            if isinstance(comp, At):
                return str(comp.qq)
        msg = event.message_str.strip()
        if msg.startswith("比划比划"):
            target_name = msg[len("比划比划"):].strip()
            if target_name:
                group_id = str(event.message_obj.group_id)
                group_data = self.get_group_data(group_id)
                for user_id, user_data in group_data.items():
                    if re.search(target_name, user_data.get('nickname', ''), re.IGNORECASE):
                        return user_id
        return None
    # endregion

    # region 事件处理
    @event_message_type(EventMessageType.ALL)
    async def on_all_messages(self, event: AstrMessageEvent):
        """消息处理器"""
        if not hasattr(event.message_obj, "group_id"):
            return

        group_id = str(event.message_obj.group_id)
        msg = event.message_str.strip()
        handler_map = {
    "牛牛菜单": self._show_menu,
    "牛牛开": lambda event: self._toggle_plugin(event, True),
    "牛牛关": lambda event: self._toggle_plugin(event, False),
    "注册牛牛": self._register,
    "打胶": self._dajiao,
    "我的牛牛": self._show_status,
    "比划比划": self._compare,
    "牛牛排行": self._show_ranking
}

        for cmd, handler in handler_map.items():
            if msg.startswith(cmd):
                async for result in handler(event):
                    yield result
                return

        yield event

    async def _toggle_plugin(self, event, enable):
        """开关插件"""
        group_id = str(event.message_obj.group_id)
        self.get_group_data(group_id)['plugin_enabled'] = enable
        self._save_niuniu_lengths()
        text_key = 'enable' if enable else 'disable'
        yield event.plain_result(self.niuniu_texts['system'][text_key])
    # endregion

    # region 核心功能
    async def _register(self, event):
        """注册牛牛"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()
        
        group_data = self.get_group_data(group_id)
        if user_id in group_data:
            text = self.niuniu_texts['register']['already_registered'].format(nickname=nickname)
            yield event.plain_result(text)
            return

        cfg = self.config.get('niuniu_config', {})
        group_data[user_id] = {
            'nickname': nickname,
            'length': random.randint(cfg.get('min_length', 5), cfg.get('max_length', 15)),
            'hardness': 1
        }
        self._save_niuniu_lengths()
        
        text = self.niuniu_texts['register']['success'].format(
            nickname=nickname,
            length=group_data[user_id]['length'],
            hardness=group_data[user_id]['hardness']
        )
        yield event.plain_result(text)

    async def _dajiao(self, event):
        """打胶功能"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()
        
        user_data = self.get_user_data(group_id, user_id)
        if not user_data:
            text = self.niuniu_texts['dajiao']['not_registered'].format(nickname=nickname)
            yield event.plain_result(text)
            return

        # 冷却检查
        last_time = self.last_dajiao_time.setdefault(group_id, {}).get(user_id, 0)
        on_cooldown, remaining = self.check_cooldown(last_time, self.COOLDOWN_10_MIN)
        if on_cooldown:
            mins = int(remaining // 60) + 1
            text = random.choice(self.niuniu_texts['dajiao']['cooldown']).format(
                nickname=nickname, 
                remaining=mins
            )
            yield event.plain_result(text)
            return

        # 计算变化
        change = 0
        current_time = time.time()
        elapsed = current_time - last_time

        if elapsed < self.COOLDOWN_30_MIN:  # 10-30分钟
            rand = random.random()
            if rand < 0.4:   # 40% 增加
                change = random.randint(2, 5)
            elif rand < 0.7: # 30% 减少
                change = -random.randint(1, 3)
        else:  # 30分钟后
            rand = random.random()
            if rand < 0.7:  # 70% 增加
                change = random.randint(3, 6)
                user_data['hardness'] = min(user_data['hardness'] + 1, 10)
            elif rand < 0.9: # 20% 减少
                change = -random.randint(1, 2)

        # 应用变化
        user_data['length'] = max(1, user_data['length'] + change)
        self.last_dajiao_time[group_id][user_id] = current_time
        self._save_niuniu_lengths()

        # 生成消息
        if change > 0:
            template = random.choice(self.niuniu_texts['dajiao']['increase'])
        elif change < 0:
            template = random.choice(self.niuniu_texts['dajiao']['decrease'])
        else:
            template = random.choice(self.niuniu_texts['dajiao']['no_effect'])
        
        text = template.format(nickname=nickname, change=abs(change))
        yield event.plain_result(f"{text}\n当前长度：{self.format_length(user_data['length'])}")

    async def _compare(self, event):
        """比划功能"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()
        
        # 获取自身数据
        user_data = self.get_user_data(group_id, user_id)
        if not user_data:
            yield event.plain_result(self.niuniu_texts['dajiao']['not_registered'].format(nickname=nickname))
            return

        # 解析目标
        target_id = self.parse_target(event)
        if not target_id:
            yield event.plain_result(self.niuniu_texts['compare']['no_target'].format(nickname=nickname))
            return
        
        if target_id == user_id:
            yield event.plain_result(self.niuniu_texts['compare']['self_compare'])
            return

        # 获取目标数据
        target_data = self.get_user_data(group_id, target_id)
        if not target_data:
            yield event.plain_result(self.niuniu_texts['compare']['target_not_registered'])
            return

        # 冷却检查
        compare_records = self.last_compare_time.setdefault(group_id, {}).setdefault(user_id, {})
        last_compare = compare_records.get(target_id, 0)
        on_cooldown, remaining = self.check_cooldown(last_compare, self.COMPARE_COOLDOWN)
        if on_cooldown:
            mins = int(remaining // 60) + 1
            text = self.niuniu_texts['compare']['cooldown'].format(
                nickname=nickname,
                remaining=mins
            )
            yield event.plain_result(text)
            return

        # 更新冷却时间
        compare_records[target_id] = time.time()

        # 计算胜负
        u_len = user_data['length']
        t_len = target_data['length']
        diff = abs(u_len - t_len)
        
        # 基础胜率
        base_win = 0.5
        if diff > 0:
            base_win = 0.7 if u_len > t_len else 0.3
        
        # 硬度影响
        hardness_factor = (user_data['hardness'] - target_data['hardness']) * 0.05
        win_prob = min(max(base_win + hardness_factor, 0.1), 0.9)

        # 执行判定
        if random.random() < win_prob:
            gain = random.randint(1, 3)
            loss = random.randint(1, 2)
            user_data['length'] += gain
            target_data['length'] = max(1, target_data['length'] - loss)
            text = random.choice(self.niuniu_texts['compare']['win']).format(
                nickname=nickname,
                target_nickname=target_data['nickname'],
                gain=gain
            )
        else:
            gain = random.randint(1, 3)
            loss = random.randint(1, 2)
            target_data['length'] += gain
            user_data['length'] = max(1, user_data['length'] - loss)
            text = random.choice(self.niuniu_texts['compare']['lose']).format(
                nickname=nickname,
                target_nickname=target_data['nickname'],
                loss=loss
            )
        
        # 硬度衰减
        if random.random() < 0.3:
            user_data['hardness'] = max(1, user_data['hardness'] - 1)
        if random.random() < 0.3:
            target_data['hardness'] = max(1, target_data['hardness'] - 1)
        
        self._save_niuniu_lengths()
        
        # 生成结果消息
        result_msg = [
            f"⚔️ 【牛牛对决结果】 ⚔️",
            f"🗡️ {nickname}: {self.format_length(user_data['length'] - gain)} > {self.format_length(user_data['length'])}",
            f"🛡️ {target_data['nickname']}: {self.format_length(target_data['length'] + loss)} > {self.format_length(target_data['length'])}",
            f"📢 {text}"
        ]
        
        # 添加特殊事件
        if abs(u_len - t_len) <= 5:
            result_msg.append("💥 双方势均力敌！")
        elif (user_data['hardness'] <= 2 and target_data['hardness'] <= 2) and random.random() < 0.2:
            result_msg.append("💢 双方牛牛因过于柔软发生缠绕，长度减半！")
            user_data['length'] = max(1, user_data['length'] // 2)
            target_data['length'] = max(1, target_data['length'] // 2)
            self._save_niuniu_lengths()
        
        yield event.plain_result("\n".join(result_msg))

    async def _show_status(self, event):
        """查看牛牛状态"""
        group_id = str(event.message_obj.group_id)
        user_id = str(event.get_sender_id())
        nickname = event.get_sender_name()
        
        user_data = self.get_user_data(group_id, user_id)
        if not user_data:
            yield event.plain_result(self.niuniu_texts['my_niuniu']['not_registered'].format(nickname=nickname))
            return

        # 评价系统
        length = user_data['length']
        length_str = self.format_length(length)
        if length < 10:
            evaluation = random.choice(self.niuniu_texts['my_niuniu']['evaluation']['short'])
        elif length < 20:
            evaluation = random.choice(self.niuniu_texts['my_niuniu']['evaluation']['medium'])
        elif length < 50:
            evaluation = random.choice(self.niuniu_texts['my_niuniu']['evaluation']['long'])
        else:
            evaluation = random.choice(self.niuniu_texts['my_niuniu']['evaluation']['very_long'])

        text = self.niuniu_texts['my_niuniu']['info'].format(
            nickname=nickname,
            length_str=length_str,
            hardness=user_data['hardness'],
            evaluation=evaluation
        )
        yield event.plain_result(text)

    async def _show_ranking(self, event):
        """显示排行榜"""
        group_id = str(event.message_obj.group_id)
        group_data = self.get_group_data(group_id)
        
        # 过滤有效用户数据
        valid_users = [
            (uid, data) for uid, data in group_data.items() 
            if isinstance(data, dict) and 'length' in data
        ]
        
        if not valid_users:
            yield event.plain_result(self.niuniu_texts['ranking']['no_data'])
            return

        # 排序并取前10
        sorted_users = sorted(valid_users, key=lambda x: x[1]['length'], reverse=True)[:10]
        
        # 构建排行榜
        ranking = [self.niuniu_texts['ranking']['header']]
        for idx, (uid, data) in enumerate(sorted_users, 1):
            ranking.append(
                self.niuniu_texts['ranking']['item'].format(
                    rank=idx,
                    name=data['nickname'],
                    length=self.format_length(data['length'])
                )
            )
        
        yield event.plain_result("\n".join(ranking))

    async def _show_menu(self, event):
        """显示菜单"""
        yield event.plain_result(self.niuniu_texts['menu']['default'])
