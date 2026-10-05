"""Диалоги."""
from .base_dialog import BaseDialog
from .device_edit import DeviceEditDialog
from .connection import ConnectionDialog
from .channel import ChannelCreationDialog
from .groups import GroupManagementDialog
from .selectors import DeviceSelectorDialog

__all__ = [
    "BaseDialog", "DeviceEditDialog", "ConnectionDialog",
    "ChannelCreationDialog", "GroupManagementDialog",
    "DeviceSelectorDialog",
]