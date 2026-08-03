from typing import Optional, List
from common.protocol import Message, MessageType


class SyncService:
    """Сервис синхронизации клиентов"""

    def __init__(self, state, tcp_server):
        self.state = state
        self.tcp_server = tcp_server

    def broadcast_to_sector(self, sector_id: int, message: Message,
                            exclude_user_id: int = 0):
        """Рассылка сообщения всем пользователям в секторе"""
        sector = self.state.get_sector(sector_id)
        if not sector:
            return

        for user_id in sector.active_users:
            if user_id == exclude_user_id:
                continue

            user = self.state.get_user(user_id)
            if user and user.is_online:
                self.tcp_server.send_to_user(user_id, message)

    def send_to_user(self, user_id: int, message: Message):
        """Отправка сообщения конкретному пользователю"""
        self.tcp_server.send_to_user(user_id, message)

    def send_full_state(self, user_id: int, view_mode: str = 'full',
                        sector_ids: List[int] = None):
        """Отправка полного состояния сети пользователю"""
        state = self.state.get_state_for_user(user_id, view_mode, sector_ids)

        # Добавляем информацию о пользователях
        users_info = []
        for sector in self.state.sectors.values():
            for uid in sector.active_users:
                u = self.state.get_user(uid)
                if u and u.id not in [x.get('id') for x in users_info]:
                    users_info.append(u.to_dict())

        state['users'] = users_info

        # Логируем для отладки
        print(f"Отправка состояния пользователю {user_id}:")
        print(f"  - Устройств: {len(state.get('devices', []))}")
        print(f"  - Соединений: {len(state.get('connections', []))}")
        print(f"  - Секторов: {len(state.get('sectors', []))}")
        print(f"  - Групп: {len(state.get('groups', []))}")

        message = Message(
            type=MessageType.FULL_STATE,
            sender_id=0,
            payload=state
        )
        self.send_to_user(user_id, message)

    def broadcast_delta(self, sector_id: int, changes: list, user_id: int):
        """Отправка изменений всем в секторе"""
        sector = self.state.get_sector(sector_id)
        if not sector:
            return

        message = Message(
            type=MessageType.DELTA_UPDATE,
            sender_id=user_id,
            sector_id=sector_id,
            payload={
                'changes': changes,
                'sector_version': sector.version,
                'global_version': self.state.global_version
            }
        )

        self.broadcast_to_sector(sector_id, message, exclude_user_id=user_id)

    def broadcast_to_all(self, message: Message, exclude_user_id: int = 0):
        """Рассылка всем подключенным пользователям"""
        for user in self.state.users.values():
            if user.id != exclude_user_id and user.is_online:
                self.send_to_user(user.id, message)