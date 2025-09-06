#!/usr/bin/env python3
"""
多实例AI角色管理器 - 每个AI角色对应一个独立的VRChat实例
"""

import threading
import time
from typing import Dict, List, Optional
from ..osc_client import OSCClient
from ..vrc_instance import VRCInstanceManager, VRCInstance
from .ai_character import AICharacter, AIPersonality
from .avatar_controller import AvatarController


class MultiInstanceAIManager:
    """多实例AI角色管理器"""
    
    def __init__(self, voicevox_client=None, vrc_exe_path: str = None):
        """初始化多实例AI管理器
        
        Args:
            voicevox_client: VOICEVOX客户端
            vrc_exe_path: VRChat可执行文件路径
        """
        self.voicevox_client = voicevox_client
        self.vrc_exe_path = vrc_exe_path
        
        # VRC实例管理器
        self.vrc_manager = VRCInstanceManager()
        
        # AI角色和其对应的控制器
        self.ai_characters: Dict[str, AICharacter] = {}
        self.avatar_controllers: Dict[str, AvatarController] = {}  # 每个AI角色的Avatar控制器
        self.osc_clients: Dict[str, OSCClient] = {}  # 每个AI角色的OSC客户端
        
        # 状态管理
        self.active_characters: Dict[str, bool] = {}  # AI角色激活状态
        
        print("多实例AI角色管理器已初始化")
    
    def create_ai_character_with_instance(self, 
                                        name: str, 
                                        personality: AIPersonality = AIPersonality.FRIENDLY,
                                        auto_start_vrc: bool = True,
                                        avatar_id: str = "",
                                        world_id: str = "") -> bool:
        """创建AI角色并分配VRC实例
        
        Args:
            name: AI角色名称
            personality: AI人格类型
            auto_start_vrc: 是否自动启动VRC实例
            avatar_id: 默认Avatar ID
            world_id: 默认世界ID
            
        Returns:
            bool: 是否成功创建
        """
        if name in self.ai_characters:
            print(f"AI角色 '{name}' 已存在")
            return False
        
        try:
            # 1. 创建VRC实例
            instance_id = self.vrc_manager.create_instance(
                ai_character_name=name,
                vrc_exe_path=self.vrc_exe_path,
                avatar_id=avatar_id,
                world_id=world_id
            )
            
            instance = self.vrc_manager.instances[instance_id]
            
            # 2. 创建专用OSC客户端
            osc_client = OSCClient(
                host="127.0.0.1",
                send_port=instance.osc_send_port,
                receive_port=instance.osc_receive_port
            )
            
            # 3. 创建Avatar控制器
            avatar_controller = AvatarController(
                osc_client=osc_client,
                voicevox_client=self.voicevox_client
            )
            
            # 4. 创建AI角色
            ai_character = AICharacter(
                name=name,
                personality=personality,
                avatar_controller=avatar_controller,
                voicevox_client=self.voicevox_client
            )
            
            # 5. 存储引用
            self.ai_characters[name] = ai_character
            self.avatar_controllers[name] = avatar_controller
            self.osc_clients[name] = osc_client
            self.active_characters[name] = False
            
            print(f"AI角色 '{name}' 创建成功，VRC实例: {instance_id}")
            print(f"OSC端口: 发送={instance.osc_send_port}, 接收={instance.osc_receive_port}")
            
            # 6. 可选：自动启动VRC实例
            if auto_start_vrc:
                success = self.start_vrc_instance_for_character(name)
                if success:
                    print(f"AI角色 '{name}' 的VRC实例启动成功")
                else:
                    print(f"AI角色 '{name}' 的VRC实例启动失败")
            
            return True
            
        except Exception as e:
            print(f"创建AI角色 '{name}' 失败: {e}")
            # 清理已创建的资源
            self.cleanup_character(name)
            return False
    
    def start_vrc_instance_for_character(self, name: str) -> bool:
        """为AI角色启动VRC实例"""
        instance = self.vrc_manager.get_instance_by_ai_character(name)
        if not instance:
            print(f"未找到AI角色 '{name}' 对应的VRC实例")
            return False
        
        success = self.vrc_manager.start_instance(instance.instance_id)
        if success:
            # 启动OSC服务器
            osc_client = self.osc_clients.get(name)
            if osc_client:
                osc_client.start_server()
                # 等待VRC实例完全启动
                time.sleep(5)
        
        return success
    
    def stop_vrc_instance_for_character(self, name: str) -> bool:
        """停止AI角色的VRC实例"""
        instance = self.vrc_manager.get_instance_by_ai_character(name)
        if not instance:
            return False
        
        # 停止OSC客户端
        osc_client = self.osc_clients.get(name)
        if osc_client:
            osc_client.stop_server()
        
        return self.vrc_manager.stop_instance(instance.instance_id)
    
    def activate_ai_character(self, name: str) -> bool:
        """激活AI角色"""
        if name not in self.ai_characters:
            print(f"AI角色 '{name}' 不存在")
            return False
        
        if self.active_characters.get(name, False):
            print(f"AI角色 '{name}' 已经激活")
            return True
        
        try:
            ai_character = self.ai_characters[name]
            
            # 确保VRC实例正在运行
            instance = self.vrc_manager.get_instance_by_ai_character(name)
            if instance and instance.status != "running":
                print(f"启动AI角色 '{name}' 的VRC实例...")
                if not self.start_vrc_instance_for_character(name):
                    print(f"无法启动VRC实例，AI角色 '{name}' 激活失败")
                    return False
            
            # 激活AI行为
            success = ai_character.start_ai_behavior()
            if success:
                self.active_characters[name] = True
                print(f"AI角色 '{name}' 已激活")
            
            return success
            
        except Exception as e:
            print(f"激活AI角色 '{name}' 失败: {e}")
            return False
    
    def deactivate_ai_character(self, name: str) -> bool:
        """停用AI角色"""
        if name not in self.ai_characters:
            return False
        
        try:
            ai_character = self.ai_characters[name]
            ai_character.stop_ai_behavior()
            self.active_characters[name] = False
            print(f"AI角色 '{name}' 已停用")
            return True
            
        except Exception as e:
            print(f"停用AI角色 '{name}' 失败: {e}")
            return False
    
    def remove_ai_character(self, name: str) -> bool:
        """删除AI角色（包括VRC实例）"""
        if name not in self.ai_characters:
            return False
        
        try:
            # 1. 停用AI角色
            self.deactivate_ai_character(name)
            
            # 2. 停止并删除VRC实例
            instance = self.vrc_manager.get_instance_by_ai_character(name)
            if instance:
                self.vrc_manager.remove_instance(instance.instance_id)
            
            # 3. 清理资源
            self.cleanup_character(name)
            
            print(f"AI角色 '{name}' 已完全删除")
            return True
            
        except Exception as e:
            print(f"删除AI角色 '{name}' 失败: {e}")
            return False
    
    def cleanup_character(self, name: str):
        """清理AI角色的所有资源"""
        # 停止OSC客户端
        if name in self.osc_clients:
            self.osc_clients[name].stop_server()
            del self.osc_clients[name]
        
        # 删除其他引用
        if name in self.ai_characters:
            del self.ai_characters[name]
        if name in self.avatar_controllers:
            del self.avatar_controllers[name]
        if name in self.active_characters:
            del self.active_characters[name]
    
    def make_character_speak(self, name: str, text: str, emotion: str = "neutral") -> bool:
        """让指定AI角色说话"""
        if name not in self.ai_characters:
            return False
        
        if not self.active_characters.get(name, False):
            print(f"AI角色 '{name}' 未激活")
            return False
        
        ai_character = self.ai_characters[name]
        ai_character.say(text, emotion)
        return True
    
    def make_character_greet(self, name: str, target_name: str = "") -> bool:
        """让指定AI角色打招呼"""
        if name not in self.ai_characters:
            return False
        
        if not self.active_characters.get(name, False):
            print(f"AI角色 '{name}' 未激活")
            return False
        
        ai_character = self.ai_characters[name]
        ai_character.greet_someone(target_name)
        return True
    
    def get_ai_character_names(self) -> List[str]:
        """获取所有AI角色名称"""
        return list(self.ai_characters.keys())
    
    def get_active_character_names(self) -> List[str]:
        """获取激活的AI角色名称"""
        return [name for name, active in self.active_characters.items() if active]
    
    def get_character_status(self, name: str) -> dict:
        """获取AI角色状态"""
        if name not in self.ai_characters:
            return {"error": "AI角色不存在"}
        
        # VRC实例状态
        instance = self.vrc_manager.get_instance_by_ai_character(name)
        vrc_status = self.vrc_manager.get_instance_status(instance.instance_id) if instance else {}
        
        # AI角色状态
        ai_character = self.ai_characters[name]
        
        return {
            "name": name,
            "personality": ai_character.personality.value,
            "ai_active": self.active_characters.get(name, False),
            "vrc_instance": vrc_status,
            "osc_ports": {
                "send": instance.osc_send_port if instance else None,
                "receive": instance.osc_receive_port if instance else None
            } if instance else {}
        }
    
    def get_all_character_status(self) -> Dict[str, dict]:
        """获取所有AI角色状态"""
        status = {}
        for name in self.ai_characters.keys():
            status[name] = self.get_character_status(name)
        return status
    
    def update_voicevox_client(self, voicevox_client):
        """更新VOICEVOX客户端引用"""
        self.voicevox_client = voicevox_client
        
        # 更新所有Avatar控制器和AI角色的VOICEVOX引用
        for avatar_controller in self.avatar_controllers.values():
            avatar_controller.set_voicevox_client(voicevox_client)
        
        for ai_character in self.ai_characters.values():
            ai_character.voicevox_client = voicevox_client
    
    def cleanup_all(self):
        """清理所有资源"""
        # 停用所有AI角色
        for name in list(self.ai_characters.keys()):
            self.deactivate_ai_character(name)
        
        # 清理所有VRC实例
        self.vrc_manager.cleanup_all_instances()
        
        # 清理本地引用
        self.ai_characters.clear()
        self.avatar_controllers.clear()
        self.osc_clients.clear()
        self.active_characters.clear()
        
        print("所有AI角色和VRC实例已清理")