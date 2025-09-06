#!/usr/bin/env python3
"""
VRChat实例管理器 - 管理多个VRChat客户端实例
每个AI角色可以对应一个独立的VRChat实例
"""

import subprocess
import psutil
import time
import json
import os
import socket
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class VRCInstance:
    """VRC实例配置"""
    instance_id: str           # 实例ID
    ai_character_name: str     # 绑定的AI角色名称
    process: Optional[subprocess.Popen] = None  # VRC进程
    osc_send_port: int = 9000      # OSC发送端口
    osc_receive_port: int = 9001   # OSC接收端口
    vrc_exe_path: str = ""         # VRC可执行文件路径
    steam_id: Optional[str] = None # Steam ID (如果通过Steam启动)
    launch_args: List[str] = None  # 启动参数
    status: str = "stopped"        # 状态: stopped, starting, running, error
    auto_login: bool = False       # 是否自动登录
    login_username: str = ""       # 登录用户名
    login_password: str = ""       # 登录密码（加密存储）
    avatar_id: str = ""            # 默认Avatar ID
    world_id: str = ""             # 默认世界ID
    
    def __post_init__(self):
        if self.launch_args is None:
            self.launch_args = []


class VRCInstanceManager:
    """VRChat实例管理器"""
    
    def __init__(self, config_file: str = "data/vrc_instances.json"):
        """初始化VRC实例管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.instances: Dict[str, VRCInstance] = {}
        self.port_range_start = 9000  # OSC端口起始范围
        self.port_range_end = 9100    # OSC端口结束范围
        
        # 确保配置目录存在
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        # 加载实例配置
        self.load_instances()
        
        # 检测VRChat安装路径
        self.detect_vrchat_path()
    
    def detect_vrchat_path(self) -> Optional[str]:
        """检测VRChat安装路径"""
        possible_paths = [
            # Steam默认安装路径
            r"C:\Program Files (x86)\Steam\steamapps\common\VRChat\VRChat.exe",
            r"D:\Steam\steamapps\common\VRChat\VRChat.exe",
            r"E:\Steam\steamapps\common\VRChat\VRChat.exe",
            # Oculus Store路径
            r"C:\Program Files\Oculus\Software\vrchat-vrchat\VRChat.exe",
            # 其他可能的路径
            r"C:\Program Files\VRChat\VRChat.exe",
            r"D:\VRChat\VRChat.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                print(f"检测到VRChat安装路径: {path}")
                return path
        
        # 尝试从注册表读取Steam路径
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")
            steam_path = winreg.QueryValueEx(key, "InstallPath")[0]
            vrchat_path = os.path.join(steam_path, "steamapps", "common", "VRChat", "VRChat.exe")
            if os.path.exists(vrchat_path):
                print(f"从注册表检测到VRChat路径: {vrchat_path}")
                return vrchat_path
        except Exception:
            pass
        
        print("未能自动检测VRChat安装路径，请手动配置")
        return None
    
    def allocate_ports(self) -> Tuple[int, int]:
        """分配可用的OSC端口对"""
        used_ports = set()
        
        # 收集已使用的端口
        for instance in self.instances.values():
            used_ports.add(instance.osc_send_port)
            used_ports.add(instance.osc_receive_port)
        
        # 查找可用端口对
        for port in range(self.port_range_start, self.port_range_end - 1, 2):
            if port not in used_ports and (port + 1) not in used_ports:
                if self.is_port_available(port) and self.is_port_available(port + 1):
                    return port, port + 1
        
        raise RuntimeError("无法分配可用的OSC端口对")
    
    def is_port_available(self, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(('localhost', port))
                return True
        except OSError:
            return False
    
    def create_instance(self, ai_character_name: str, 
                       vrc_exe_path: str = None,
                       auto_login: bool = False,
                       login_username: str = "",
                       avatar_id: str = "",
                       world_id: str = "") -> str:
        """创建新的VRC实例
        
        Args:
            ai_character_name: 绑定的AI角色名称
            vrc_exe_path: VRC可执行文件路径
            auto_login: 是否自动登录
            login_username: 登录用户名
            avatar_id: 默认Avatar ID
            world_id: 默认世界ID
            
        Returns:
            str: 实例ID
        """
        # 生成实例ID
        instance_id = f"vrc_instance_{ai_character_name}_{int(time.time())}"
        
        # 检查AI角色名称是否已被使用
        for instance in self.instances.values():
            if instance.ai_character_name == ai_character_name:
                raise ValueError(f"AI角色 '{ai_character_name}' 已绑定到实例: {instance.instance_id}")
        
        # 分配端口
        send_port, receive_port = self.allocate_ports()
        
        # 使用检测到的VRC路径或用户提供的路径
        if not vrc_exe_path:
            vrc_exe_path = self.detect_vrchat_path()
            if not vrc_exe_path:
                raise ValueError("未找到VRChat安装路径，请手动指定")
        
        # 创建实例配置
        instance = VRCInstance(
            instance_id=instance_id,
            ai_character_name=ai_character_name,
            osc_send_port=send_port,
            osc_receive_port=receive_port,
            vrc_exe_path=vrc_exe_path,
            auto_login=auto_login,
            login_username=login_username,
            avatar_id=avatar_id,
            world_id=world_id,
            launch_args=[]
        )
        
        self.instances[instance_id] = instance
        self.save_instances()
        
        print(f"创建VRC实例: {instance_id} (AI角色: {ai_character_name}, OSC: {send_port}/{receive_port})")
        return instance_id
    
    def start_instance(self, instance_id: str) -> bool:
        """启动VRC实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            bool: 是否成功启动
        """
        if instance_id not in self.instances:
            print(f"实例 {instance_id} 不存在")
            return False
        
        instance = self.instances[instance_id]
        
        if instance.status == "running":
            print(f"实例 {instance_id} 已在运行")
            return True
        
        try:
            # 构建启动命令
            cmd = [instance.vrc_exe_path]
            
            # 添加OSC端口参数
            cmd.extend([
                "--osc-send-port", str(instance.osc_send_port),
                "--osc-receive-port", str(instance.osc_receive_port)
            ])
            
            # 添加其他启动参数
            if instance.launch_args:
                cmd.extend(instance.launch_args)
            
            # 如果指定了世界ID，添加启动世界参数
            if instance.world_id:
                cmd.extend(["--url", f"vrchat://launch?worldId={instance.world_id}"])
            
            print(f"启动VRC实例命令: {' '.join(cmd)}")
            
            # 启动进程
            instance.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            
            instance.status = "starting"
            
            # 等待一段时间检查进程是否正常启动
            time.sleep(3)
            
            if instance.process.poll() is None:
                instance.status = "running"
                print(f"VRC实例 {instance_id} 启动成功 (PID: {instance.process.pid})")
                return True
            else:
                instance.status = "error"
                stdout, stderr = instance.process.communicate()
                print(f"VRC实例 {instance_id} 启动失败:")
                print(f"STDOUT: {stdout.decode()}")
                print(f"STDERR: {stderr.decode()}")
                return False
                
        except Exception as e:
            instance.status = "error"
            print(f"启动VRC实例 {instance_id} 时出错: {e}")
            return False
    
    def stop_instance(self, instance_id: str) -> bool:
        """停止VRC实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            bool: 是否成功停止
        """
        if instance_id not in self.instances:
            return False
        
        instance = self.instances[instance_id]
        
        try:
            if instance.process and instance.process.poll() is None:
                # 优雅地终止进程
                instance.process.terminate()
                
                # 等待进程终止
                try:
                    instance.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # 如果优雅终止失败，强制杀死进程
                    instance.process.kill()
                    instance.process.wait()
                
                print(f"VRC实例 {instance_id} 已停止")
            
            instance.process = None
            instance.status = "stopped"
            return True
            
        except Exception as e:
            print(f"停止VRC实例 {instance_id} 时出错: {e}")
            return False
    
    def remove_instance(self, instance_id: str) -> bool:
        """删除VRC实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            bool: 是否成功删除
        """
        if instance_id not in self.instances:
            return False
        
        # 先停止实例
        self.stop_instance(instance_id)
        
        # 删除实例配置
        del self.instances[instance_id]
        self.save_instances()
        
        print(f"已删除VRC实例: {instance_id}")
        return True
    
    def get_instance_by_ai_character(self, ai_character_name: str) -> Optional[VRCInstance]:
        """根据AI角色名称获取实例"""
        for instance in self.instances.values():
            if instance.ai_character_name == ai_character_name:
                return instance
        return None
    
    def list_instances(self) -> List[VRCInstance]:
        """获取所有实例列表"""
        return list(self.instances.values())
    
    def get_instance_status(self, instance_id: str) -> dict:
        """获取实例状态信息"""
        if instance_id not in self.instances:
            return {"error": "实例不存在"}
        
        instance = self.instances[instance_id]
        
        # 检查进程是否仍在运行
        if instance.process:
            if instance.process.poll() is None:
                instance.status = "running"
            else:
                instance.status = "stopped"
                instance.process = None
        
        return {
            "instance_id": instance.instance_id,
            "ai_character_name": instance.ai_character_name,
            "status": instance.status,
            "osc_send_port": instance.osc_send_port,
            "osc_receive_port": instance.osc_receive_port,
            "process_id": instance.process.pid if instance.process else None
        }
    
    def load_instances(self):
        """从文件加载实例配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for instance_data in data.get("instances", []):
                    instance = VRCInstance(**instance_data)
                    self.instances[instance.instance_id] = instance
                    
                print(f"加载了 {len(self.instances)} 个VRC实例配置")
        except Exception as e:
            print(f"加载VRC实例配置失败: {e}")
    
    def save_instances(self):
        """保存实例配置到文件"""
        try:
            instances_data = []
            for instance in self.instances.values():
                # 不保存运行时状态
                instance_dict = {
                    "instance_id": instance.instance_id,
                    "ai_character_name": instance.ai_character_name,
                    "osc_send_port": instance.osc_send_port,
                    "osc_receive_port": instance.osc_receive_port,
                    "vrc_exe_path": instance.vrc_exe_path,
                    "steam_id": instance.steam_id,
                    "launch_args": instance.launch_args,
                    "auto_login": instance.auto_login,
                    "login_username": instance.login_username,
                    "login_password": instance.login_password,  # 注意：实际应用中应加密存储
                    "avatar_id": instance.avatar_id,
                    "world_id": instance.world_id
                }
                instances_data.append(instance_dict)
            
            data = {
                "version": "1.0",
                "instances": instances_data,
                "updated": time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"保存VRC实例配置失败: {e}")
    
    def cleanup_all_instances(self):
        """清理所有实例"""
        for instance_id in list(self.instances.keys()):
            self.stop_instance(instance_id)
        
        print("已清理所有VRC实例")