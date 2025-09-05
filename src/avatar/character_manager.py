#!/usr/bin/env python3
"""
角色管理器 - 管理VRChat中的角色位置和距离追踪
"""

import json
import os
import math
from typing import Dict, List, Tuple, Optional, Callable


class CharacterManager:
    """角色管理器类"""
    
    def __init__(self, data_file: str = "data/vrc_characters.json"):
        """初始化角色管理器
        
        Args:
            data_file: 角色数据存储文件路径
        """
        self.data_file = data_file
        self.characters: Dict[str, Dict[str, float]] = {}  # {name: {"x": float, "y": float, "z": float}}
        self.player_position = {"x": 0.0, "y": 0.0, "z": 0.0}
        self.position_callbacks: List[Callable] = []  # 位置更新回调函数
        
        # 创建数据目录
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        
        # 加载已保存的角色数据
        self.load_characters()
    
    def add_character(self, name: str, x: float, y: float, z: float) -> bool:
        """添加新角色
        
        Args:
            name: 角色名称
            x, y, z: 角色坐标
            
        Returns:
            bool: 是否成功添加
        """
        if not name.strip():
            return False
            
        self.characters[name] = {"x": float(x), "y": float(y), "z": float(z)}
        self.save_characters()
        return True
    
    def remove_character(self, name: str) -> bool:
        """删除角色
        
        Args:
            name: 角色名称
            
        Returns:
            bool: 是否成功删除
        """
        if name in self.characters:
            del self.characters[name]
            self.save_characters()
            return True
        return False
    
    def update_character_position(self, name: str, x: float, y: float, z: float) -> bool:
        """更新角色位置
        
        Args:
            name: 角色名称
            x, y, z: 新坐标
            
        Returns:
            bool: 是否成功更新
        """
        if name in self.characters:
            self.characters[name] = {"x": float(x), "y": float(y), "z": float(z)}
            self.save_characters()
            return True
        return False
    
    def update_player_position(self, x: float, y: float, z: float):
        """更新玩家位置
        
        Args:
            x, y, z: 玩家坐标
        """
        self.player_position = {"x": float(x), "y": float(y), "z": float(z)}
        
        # 调用所有位置更新回调函数
        for callback in self.position_callbacks:
            try:
                callback(x, y, z)
            except Exception as e:
                print(f"位置回调函数执行错误: {e}")
    
    def calculate_distance(self, pos1: Dict[str, float], pos2: Dict[str, float]) -> float:
        """计算3D距离
        
        Args:
            pos1: 位置1 {"x": float, "y": float, "z": float}
            pos2: 位置2 {"x": float, "y": float, "z": float}
            
        Returns:
            float: 3D距离
        """
        dx = pos1['x'] - pos2['x']
        dy = pos1['y'] - pos2['y']
        dz = pos1['z'] - pos2['z']
        return math.sqrt(dx*dx + dy*dy + dz*dz)
    
    def get_character_distances(self) -> Dict[str, float]:
        """获取所有角色与玩家的距离
        
        Returns:
            Dict[str, float]: 角色名称与距离的映射
        """
        distances = {}
        for name, pos in self.characters.items():
            distances[name] = self.calculate_distance(self.player_position, pos)
        return distances
    
    def get_nearest_characters(self, count: int = 3) -> List[Tuple[str, float]]:
        """获取最近的N个角色
        
        Args:
            count: 返回角色数量
            
        Returns:
            List[Tuple[str, float]]: [(角色名, 距离), ...] 按距离排序
        """
        distances = self.get_character_distances()
        sorted_distances = sorted(distances.items(), key=lambda x: x[1])
        return sorted_distances[:count]
    
    def get_characters_in_range(self, max_distance: float) -> List[Tuple[str, float]]:
        """获取指定范围内的角色
        
        Args:
            max_distance: 最大距离
            
        Returns:
            List[Tuple[str, float]]: [(角色名, 距离), ...]
        """
        distances = self.get_character_distances()
        in_range = [(name, dist) for name, dist in distances.items() if dist <= max_distance]
        return sorted(in_range, key=lambda x: x[1])
    
    def get_all_characters(self) -> Dict[str, Dict[str, float]]:
        """获取所有角色信息"""
        return self.characters.copy()
    
    def get_player_position(self) -> Dict[str, float]:
        """获取玩家当前位置"""
        return self.player_position.copy()
    
    def add_position_callback(self, callback: Callable):
        """添加位置更新回调函数
        
        Args:
            callback: 回调函数，签名为 callback(x: float, y: float, z: float)
        """
        if callback not in self.position_callbacks:
            self.position_callbacks.append(callback)
    
    def remove_position_callback(self, callback: Callable):
        """移除位置更新回调函数"""
        if callback in self.position_callbacks:
            self.position_callbacks.remove(callback)
    
    def save_characters(self):
        """保存角色数据到文件"""
        try:
            data = {
                'characters': self.characters,
                'player_position': self.player_position,
                'version': '1.0'
            }
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存角色数据失败: {e}")
    
    def load_characters(self):
        """从文件加载角色数据"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.characters = data.get('characters', {})
                    self.player_position = data.get('player_position', {"x": 0.0, "y": 0.0, "z": 0.0})
            else:
                # 创建空的数据文件
                self.save_characters()
        except Exception as e:
            print(f"加载角色数据失败: {e}")
            self.characters = {}
            self.player_position = {"x": 0.0, "y": 0.0, "z": 0.0}
    
    def get_character_count(self) -> int:
        """获取角色数量"""
        return len(self.characters)
    
    def character_exists(self, name: str) -> bool:
        """检查角色是否存在"""
        return name in self.characters
    
    def get_distance_info_text(self, max_characters: int = 5) -> str:
        """获取距离信息的文本表示
        
        Args:
            max_characters: 最大显示角色数
            
        Returns:
            str: 格式化的距离信息文本
        """
        if not self.characters:
            return "暂无角色数据\n点击添加角色按钮开始"
        
        nearest = self.get_nearest_characters(max_characters)
        lines = []
        
        for name, distance in nearest:
            lines.append(f"• {name}: {distance:.2f}m")
        
        return "\n".join(lines)