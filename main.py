import random
import yaml
import os
import re
import time
from astrbot.api.all import *

# 定义 YAML 文件路径
PLUGIN_DIR = os.path.join('data', 'plugins', 'astrbot_plugin_niuniu')
if not os.path.exists(PLUGIN_DIR):
    os.makedirs(PLUGIN_DIR)
# 将牛牛长度文件路径设置到 astrbot_plugin_niuniu 之前的 data 文件夹
NIUNIU_LENGTHS_FILE = os.path.join('data', 'niuniu_lengths.yml')
NIUNIU_TEXTS_FILE = os.path.join(PLUGIN_DIR, 'niuniu_game_texts.yml')


@register("niuniu_plugin", "长安某", "牛牛插件，包含注册牛牛、打胶、我的牛牛、比划比划、牛牛排行等功能", "3.0.0")
class NiuniuPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        if config is None:
            config = {}
        self.config = config
        self.niuniu_lengths = self._load_niuniu_lengths()
        self.niuniu_texts = self._load_niuniu_texts()
        # 记录每个用户的上次打胶时间和冷却时长
        self.last_dajiao_time = {}
        # 记录每个群中每个用户在 10 分钟内主动邀请的人数，格式为 {group_id: {user_id: (last_time, invited_count)}}
        self.invite_count = {}
        # 记录每个群中每个用户发起比划的冷却信息，格式为 {group_id: {user_id: {target_id: last_time}}}
        self.last_compare_time = {}
        # 初始化开关状态，默认为开
        self.plugin_enabled = self.niuniu_lengths.get('plugin_enabled', True)

    def _create_niuniu_lengths_file(self):
        """创建 niuniu_lengths.yml 文件"""
        if not os.path.exists(NIUNIU_LENGTHS_FILE):
            with open(NIUNIU_LENGTHS_FILE, 'w', encoding='utf-8') as file:
                data = {'plugin_enabled': True}
                yaml.dump(data, file, allow_unicode=True)

    def _load_niuniu_lengths(self):
        """从 YAML 文件中加载牛牛长度数据和开关状态"""
        self._create_niuniu_lengths_file()
        encodings = ['utf-8', 'gbk2312']
        for encoding in encodings:
            try:
                with open(NIUNIU_LENGTHS_FILE, 'r', encoding=encoding) as file:
                    data = yaml.safe_load(file) or {}
                    # 确保 plugin_enabled 键存在，默认为 True
                    data.setdefault('plugin_enabled', True)
                    return data
            except UnicodeDecodeError:
                continue
            except FileNotFoundError:
                return {'plugin_enabled': True}
            except Exception:
                return {'plugin_enabled': True}
        return {'plugin_enabled': True}

    def _load_niuniu_texts(self):
        """从 YAML 文件中加载游戏文本数据"""
        encodings = ['utf-8', 'gbk2312']
        for encoding in encodings:
            try:
                with open(NIUNIU_TEXTS_FILE, 'r', encoding=encoding) as file:
                    return yaml.safe_load(file) or {}
            except UnicodeDecodeError:
                continue
            except FileNotFoundError:
                return {}
            except Exception:
                return {}
        return {}

    def _save_niuniu_lengths(self):
        """将牛牛长度数据和开关状态保存到 YAML 文件"""
        encodings = ['utf-8', 'gbk2312']
        for encoding in encodings:
            try:
                with open(NIUNIU_LENGTHS_FILE, 'w', encoding=encoding) as file:
                    self.niuniu_lengths['plugin_enabled'] = self.plugin_enabled
                    yaml.dump(self.niuniu_lengths, file, allow_unicode=True)
                break
            except Exception:
                continue

    def get_niuniu_config(self):
        """获取牛牛相关配置"""
        return self.config.get('niuniu_config', {})

    def check_probability(self, probability):
        """检查是否满足给定概率条件"""
        return random.random() < probability

    def format_niuniu_message(self, message, length):
        """格式化牛牛相关消息"""
        if length >= 100:
            length_str = f"{length / 100:.2f}m"
        else:
            length_str = f"{length}cm"
        return f"{message}，当前牛牛长度为{length_str}"

    @event_message_type(EventMessageType.ALL)
    async def on_all_messages(self, event: AstrMessageEvent):
        """全局事件监听，处理所有消息"""
        group_id = event.message_obj.group_id if hasattr(event.message_obj, "group_id") else None
        if not group_id:
            return

        message_str = event.message_str.strip()

        if message_str == "牛牛开":
            self.plugin_enabled = True
            self._save_niuniu_lengths()
            yield event.plain_result("牛牛插件已开启。")
        elif message_str == "牛牛关":
            self.plugin_enabled = False
            self._save_niuniu_lengths()
            yield event.plain_result("牛牛插件已关闭，除了牛牛菜单，其他功能不可用。")
        elif message_str == "牛牛菜单":
            async for result in self.niuniu_menu(event):
                yield result
        elif self.plugin_enabled:
            if message_str == "注册牛牛":
                async for result in self.register_niuniu(event):
                    yield result
            elif message_str == "打胶":
                async for result in self.dajiao(event):
                    yield result
            elif message_str == "我的牛牛":
                async for result in self.my_niuniu(event):
                    yield result
            elif message_str.startswith("比划比划"):
                parts = message_str.split(maxsplit=1)
                target_name = parts[1].strip() if len(parts) > 1 else None
                async for result in self.compare_niuniu(event, target_name):
                    yield result
            elif message_str == "牛牛排行":
                async for result in self.niuniu_rank(event):
                    yield result

        yield event

    def parse_at_users(self, event: AstrMessageEvent):
        """解析消息中的 @ 用户"""
        chain = event.message_obj.message
        return [str(comp.qq) for comp in chain if isinstance(comp, At)]

    async def register_niuniu(self, event: AstrMessageEvent):
        """注册牛牛指令处理函数"""
        user_id = str(event.get_sender_id())
        sender_nickname = event.get_sender_name()
        group_id = event.message_obj.group_id
        if group_id:
            if group_id not in self.niuniu_lengths:
                self.niuniu_lengths[group_id] = {}
            if user_id not in self.niuniu_lengths[group_id]:
                config = self.get_niuniu_config()
                min_length = config.get('min_length', 1)
                max_length = config.get('max_length', 10)
                length = random.randint(min_length, max_length)
                # 固定硬度为 1
                hardness = 1
                self.niuniu_lengths[group_id][user_id] = {
                    "nickname": sender_nickname,
                    "length": length,
                    "hardness": hardness
                }
                self._save_niuniu_lengths()
                msg = self.niuniu_texts['register']['success'].format(nickname=sender_nickname, length=length, hardness=hardness)
                yield event.plain_result(msg)
            else:
                msg = self.niuniu_texts['register']['already_registered'].format(nickname=sender_nickname)
                yield event.plain_result(msg)
        else:
            msg = self.niuniu_texts['register']['only_group']
            yield event.plain_result(msg)

    async def dajiao(self, event: AstrMessageEvent):
        """打胶指令处理函数"""
        user_id = str(event.get_sender_id())
        sender_nickname = event.get_sender_name()
        group_id = event.message_obj.group_id
        if group_id and group_id in self.niuniu_lengths and user_id in self.niuniu_lengths[group_id]:
            user_info = self.niuniu_lengths[group_id][user_id]
            # 检查冷却期
            current_time = time.time()
            last_time = self.last_dajiao_time.get(user_id, 0)
            time_diff = current_time - last_time

            # 十分钟内不允许打胶
            MIN_COOLDOWN = 10 * 60
            if time_diff < MIN_COOLDOWN:
                message = random.choice(self.niuniu_texts['dajiao']['cooldown']).format(nickname=sender_nickname)
                yield event.plain_result(message)
                return

            # 超过十分钟但低于三十分钟
            THIRTY_MINUTES = 30 * 60
            if time_diff < THIRTY_MINUTES:
                # 10 - 30 分钟变长概率为 40%，变短概率为 30%，不变概率为 30%
                if self.check_probability(0.4):
                    config = self.get_niuniu_config()
                    max_change = config.get('max_change', 6)
                    change = random.randint(2, max_change)
                    message = random.choice(self.niuniu_texts['dajiao']['increase']).format(nickname=sender_nickname, change=change)
                elif self.check_probability(0.3):
                    # 30 分钟内打胶失败，长度减少 1 - 4
                    change = -random.randint(1, 4)
                    positive_change = -change
                    message = random.choice(self.niuniu_texts['dajiao']['decrease']).format(nickname=sender_nickname, change=positive_change)
                else:
                    message = random.choice(self.niuniu_texts['dajiao']['no_effect']).format(nickname=sender_nickname)
                    change = 0

                user_info["length"] += change
                if user_info["length"] < 1:
                    user_info["length"] = 1

                self._save_niuniu_lengths()
                # 更新上次打胶时间
                self.last_dajiao_time[user_id] = current_time
                yield event.plain_result(self.format_niuniu_message(message, user_info["length"]))
                return

            # 三十分钟后
            # 30 分钟以后变长概率为 70%，无变化概率为 10%，变短概率为 20%
            rand_num = random.random()
            if rand_num < 0.7:
                config = self.get_niuniu_config()
                max_change = 5
                change = random.randint(2, max_change)
                message = random.choice(self.niuniu_texts['dajiao']['increase']).format(nickname=sender_nickname, change=change)
            elif rand_num < 0.8:
                change = 0
                message = random.choice(self.niuniu_texts['dajiao']['no_effect']).format(nickname=sender_nickname)
            else:
                change = -random.randint(1, 2)
                positive_change = -change
                message = random.choice(self.niuniu_texts['dajiao']['decrease']).format(nickname=sender_nickname, change=positive_change)

            user_info["length"] += change
            if user_info["length"] < 1:
                user_info["length"] = 1

            # 三十分钟后打胶，硬度固定增加 2 点
            user_info["hardness"] = min(user_info["hardness"] + 2, 10)

            self._save_niuniu_lengths()
            # 更新上次打胶时间
            self.last_dajiao_time[user_id] = current_time
            yield event.plain_result(self.format_niuniu_message(message, user_info["length"]))
        else:
            message = self.niuniu_texts['dajiao']['not_registered'].format(nickname=sender_nickname)
            yield event.plain_result(message)

    async def my_niuniu(self, event: AstrMessageEvent):
        """我的牛牛指令处理函数"""
        user_id = str(event.get_sender_id())
        sender_nickname = event.get_sender_name()
        group_id = event.message_obj.group_id
        if group_id and group_id in self.niuniu_lengths and user_id in self.niuniu_lengths[group_id]:
            user_info = self.niuniu_lengths[group_id][user_id]
            length = user_info["length"]
            hardness = user_info["hardness"]

            # 根据长度给出评价
            if length <= 12:
                evaluations = self.niuniu_texts['my_niuniu']['evaluation']['short']
            elif length <= 24:
                evaluations = self.niuniu_texts['my_niuniu']['evaluation']['medium']
            elif length <= 36:
                evaluations = self.niuniu_texts['my_niuniu']['evaluation']['long']
            else:
                evaluations = self.niuniu_texts['my_niuniu']['evaluation']['very_long']

            evaluation = random.choice(evaluations)
            if length >= 100:
                length_str = f"{length / 100:.2f}m"
            else:
                length_str = f"{length}cm"
            msg = self.niuniu_texts['my_niuniu']['info'].format(nickname=sender_nickname, length_str=length_str, hardness=hardness, evaluation=evaluation)
            yield event.plain_result(msg)
        else:
            msg = self.niuniu_texts['my_niuniu']['not_registered'].format(nickname=sender_nickname)
            yield event.plain_result(msg)

    async def compare_niuniu(self, event: AstrMessageEvent, target_name: str = None):
        """比划比划指令处理函数"""
        user_id = str(event.get_sender_id())
        sender_nickname = event.get_sender_name()
        group_id = str(event.message_obj.group_id)

        if group_id and group_id in self.niuniu_lengths and user_id in self.niuniu_lengths[group_id]:
            at_users = self.parse_at_users(event)
            target_user_id = None

            if at_users:
                target_user_id = at_users[0]
            elif target_name:
                # 使用正则表达式进行模糊匹配
                pattern = re.compile(re.escape(target_name), re.IGNORECASE)
                matched_users = []
                for uid, info in self.niuniu_lengths[group_id].items():
                    if pattern.search(info["nickname"]):
                        matched_users.append(uid)
                if len(matched_users) == 0:
                    default_no_target_msg = "{nickname}，你没有指定要比划的对象哦！"
                    no_target_msg = self.niuniu_texts['compare'].get('no_target', default_no_target_msg)
                    if isinstance(no_target_msg, list):
                        no_target_msg = random.choice(no_target_msg)
                    message = no_target_msg.format(nickname=sender_nickname)
                    yield event.plain_result(message)
                    return
                elif len(matched_users) > 1:
                    yield event.plain_result(f"{sender_nickname}，找到多个包含 '{target_name}' 的用户，请使用 @ 精确指定对手。")
                    return
                else:
                    target_user_id = matched_users[0]

                    # 检查匹配到的是否是自己
                    if target_user_id == user_id:
                        yield event.plain_result(f"{sender_nickname}，你不能和自己比划。")
                        return
            else:
                default_no_target_msg = "{nickname}，你没有指定要比划的对象哦！"
                no_target_msg = self.niuniu_texts['compare'].get('no_target', default_no_target_msg)
                if isinstance(no_target_msg, list):
                    no_target_msg = random.choice(no_target_msg)
                message = no_target_msg.format(nickname=sender_nickname)
                yield event.plain_result(message)
                return

            if not target_user_id:
                default_no_target_msg = "{nickname}，你没有指定要比划的对象哦！"
                no_target_msg = self.niuniu_texts['compare'].get('no_target', default_no_target_msg)
                if isinstance(no_target_msg, list):
                    no_target_msg = random.choice(no_target_msg)
                message = no_target_msg.format(nickname=sender_nickname)
                yield event.plain_result(message)
                return

            if target_user_id not in self.niuniu_lengths[group_id]:
                default_msg = "{nickname}，对方还没有注册牛牛呢！"
                target_not_registered_msg = self.niuniu_texts['compare'].get('target_not_registered', default_msg)
                if isinstance(target_not_registered_msg, list):
                    target_not_registered_msg = random.choice(target_not_registered_msg)
                message = target_not_registered_msg.format(nickname=sender_nickname)
                yield event.plain_result(message)
                return

            # 检查 10 分钟内邀请人数限制
            current_time = time.time()
            group_invite_count = self.invite_count.setdefault(group_id, {})
            last_time, count = group_invite_count.get(user_id, (0, 0))
            if current_time - last_time < 10 * 60:
                if count >= 3:
                    default_limit_msg = "{nickname}，你在 10 分钟内邀请人数过多，暂时不能再发起比划啦！"
                    limit_msg = self.niuniu_texts['compare'].get('limit', default_limit_msg)
                    if isinstance(limit_msg, list):
                        limit_msg = random.choice(limit_msg)
                    message = limit_msg.format(nickname=sender_nickname)
                    yield event.plain_result(message)
                    return
            else:
                count = 0
            group_invite_count[user_id] = (current_time, count + 1)

            # 检查冷却
            group_compare_time = self.last_compare_time.setdefault(group_id, {})
            user_compare_time = group_compare_time.setdefault(user_id, {})
            last_compare = user_compare_time.get(target_user_id, 0)
            MIN_COMPARE_COOLDOWN = 10 * 60  # 10 分钟冷却时间
            if current_time - last_compare < MIN_COMPARE_COOLDOWN:
                default_cooldown_msg = "{nickname}，你和该对手的比划冷却时间还没到呢，请稍后再试。"
                cooldown_msg = self.niuniu_texts['compare'].get('cooldown', default_cooldown_msg)
                if isinstance(cooldown_msg, list):
                    cooldown_msg = random.choice(cooldown_msg)
                message = cooldown_msg.format(nickname=sender_nickname)
                yield event.plain_result(message)
                return

            user_info = self.niuniu_lengths[group_id][user_id]
            target_info = self.niuniu_lengths[group_id][target_user_id]
            # 更新最后发起比划时间
            user_compare_time[target_user_id] = current_time

            user_length = user_info["length"]
            target_length = target_info["length"]
            user_hardness = user_info["hardness"]
            target_hardness = target_info["hardness"]
            diff = user_length - target_length

            # 确定长短牛牛
            if user_length < target_length:
                short_info = user_info
                short_nickname = sender_nickname
                long_info = target_info
                long_nickname = target_info["nickname"]
            else:
                short_info = target_info
                short_nickname = target_info["nickname"]
                long_info = user_info
                long_nickname = sender_nickname

            length_diff = long_info["length"] - short_info["length"]

            # 计算胜率
            if length_diff <= 10:
                base_win_chance = 0.5  # 长度相近基础胜率 50%
            else:
                base_win_chance = 0.3  # 短牛牛基础胜率 30%

            # 长度对短牛牛胜率的影响
            length_influence = 0
            if length_diff > 10:
                length_influence = -min(max(length_diff * 0.01, 0.01), 0.2)  # 长度差距大，短牛牛胜率降低，最大降低 20%

            # 硬度对胜率的影响
            hardness_diff = short_info["hardness"] - long_info["hardness"]
            hardness_influence = min(max(hardness_diff * 0.01, -0.2), 0.2)  # 硬度影响范围 -20% 到 20%

            win_chance = base_win_chance + length_influence + hardness_influence
            win_chance = max(win_chance, 0.1)  # 最低胜率 10%

            config = self.get_niuniu_config()
            min_bonus = config.get('min_bonus', 0)
            max_bonus = config.get('max_bonus', 3)

            if self.check_probability(win_chance):
                bonus = random.randint(min_bonus, max_bonus)
                extra_length = 0
                if length_diff > 10 and short_info == user_info:
                    # 长度差距大于 10 且短牛牛获胜，额外获得长牛牛 20% 长度
                    extra_length = int(long_info["length"] * 0.2)
                    short_info["length"] += bonus + extra_length
                    long_info["length"] -= extra_length
                    default_short_win_msg = "{short_nickname} 以小博大，战胜了 {long_nickname}！长度增加了 {bonus}cm，还额外获得了 {extra_length}cm！"
                    short_win_msg = self.niuniu_texts['compare'].get('short_win', default_short_win_msg)
                    if isinstance(short_win_msg, list):
                        short_win_msg = random.choice(short_win_msg)
                    message = short_win_msg.format(
                        short_nickname=short_nickname, long_nickname=long_nickname, bonus=bonus, extra_length=extra_length)
                else:
                    default_win_msg = "{nickname} 在和 {target_nickname} 的比划中获胜啦！"
                    win_msg = self.niuniu_texts['compare'].get('win', default_win_msg)
                    if isinstance(win_msg, list):
                        win_msg = random.choice(win_msg)
                    message = win_msg.format(
                        nickname=short_nickname, target_nickname=long_nickname)

                self._save_niuniu_lengths()
                yield event.plain_result(self.format_niuniu_message(
                    f"{message} 你的长度增加{bonus}cm" + (f"，还额外获得了 {extra_length}cm！" if extra_length > 0 else ""),
                    short_info["length"]))
            else:
                bonus = random.randint(min_bonus, max_bonus)
                long_info["length"] += bonus
                self._save_niuniu_lengths()
                default_lose_msg = "{nickname} 在和 {target_nickname} 的比划中落败了。"
                lose_msg = self.niuniu_texts['compare'].get('lose', default_lose_msg)
                if isinstance(lose_msg, list):
                    lose_msg = random.choice(lose_msg)
                lose_message = lose_msg.format(
                    nickname=short_nickname, target_nickname=long_nickname)
                if bonus > 0:
                    target_new_length = long_info["length"]
                    if target_new_length >= 100:
                        length_str = f"{target_new_length / 100:.2f}m"
                    else:
                        length_str = f"{target_new_length}cm"
                    default_target_increase_msg = "{message} {target_nickname} 的牛牛长度增加了 {bonus}cm，现在长度为 {length_str}。"
                    target_increase_msg = self.niuniu_texts['compare'].get('target_increase', default_target_increase_msg)
                    if isinstance(target_increase_msg, list):
                        target_increase_msg = random.choice(target_increase_msg)
                    message = target_increase_msg.format(
                        message=lose_message, target_nickname=long_nickname, bonus=bonus, length_str=length_str)
                    yield event.plain_result(message)
                else:
                    default_target_no_increase_msg = "{message} {target_nickname} 的牛牛长度没有变化。"
                    target_no_increase_msg = self.niuniu_texts['compare'].get('target_no_increase', default_target_no_increase_msg)
                    if isinstance(target_no_increase_msg, list):
                        target_no_increase_msg = random.choice(target_no_increase_msg)
                    message = target_no_increase_msg.format(
                        message=lose_message, target_nickname=long_nickname)
                    yield event.plain_result(message)

            # 比划比划时，硬度 30% 概率降低 1 点
            for info in [user_info, target_info]:
                if self.check_probability(0.3):
                    info["hardness"] = max(1, info["hardness"] - 1)
            self._save_niuniu_lengths()
        else:
            default_self_not_registered_msg = "{nickname}，你还没有注册牛牛，无法进行比划哦！"
            self_not_registered_msg = self.niuniu_texts['compare'].get('not_registered', default_self_not_registered_msg)
            if isinstance(self_not_registered_msg, list):
                self_not_registered_msg = random.choice(self_not_registered_msg)
            message = self_not_registered_msg.format(nickname=sender_nickname)
            yield event.plain_result(message)

    async def niuniu_rank(self, event: AstrMessageEvent):
        """牛牛排行指令处理函数"""
        group_id = str(event.message_obj.group_id)
        if group_id in self.niuniu_lengths:
            users = self.niuniu_lengths[group_id]
            sorted_users = sorted(users.items(), key=lambda item: item[1]["length"], reverse=True)
            rank_message = "本群牛牛长度排行榜：\n"
            for i, (user_id, info) in enumerate(sorted_users, start=1):
                nickname = info["nickname"]
                length = info["length"]
                if length >= 100:
                    length_str = f"{length / 100:.2f}m"
                else:
                    length_str = f"{length}cm"
                rank_message += f"{i}. {nickname}：{length_str}\n"
            yield event.plain_result(rank_message)
        else:
            message = "本群还没有人注册牛牛呢。"
            yield event.plain_result(message)

    async def niuniu_menu(self, event: AstrMessageEvent):
        """牛牛菜单指令处理函数"""
        default_menu = "牛牛插件菜单：\n1. 注册牛牛：注册你的牛牛\n2. 打胶：尝试增加牛牛长度\n3. 我的牛牛：查看自己牛牛的长度和硬度\n4. 比划比划 [对手名称/@对手]：和其他用户比划牛牛长度\n5. 牛牛排行：查看本群牛牛长度排行榜\n6. 牛牛开：开启牛牛插件\n7. 牛牛关：关闭牛牛插件"
        menu = self.niuniu_texts.get('menu', default_menu)
        yield event.plain_result(menu)
