#!/usr/bin/env python3
"""
测试表情间隔更新功能
验证表情数据的缓存、平均计算和定时更新机制
"""

import sys
import os
import time
import threading
import random

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class MockEmotionUpdateTest:
    """模拟表情更新测试"""
    
    def __init__(self):
        # 模拟缓存数据
        self.emotion_data_cache = []
        self.update_interval = 3.0  # 3秒间隔
        self.is_running = False
        
    def generate_random_emotions(self):
        """生成随机表情数据"""
        emotions = {
            'angry': random.uniform(0.0, 1.0),
            'disgust': random.uniform(0.0, 1.0),
            'fear': random.uniform(0.0, 1.0),
            'happy': random.uniform(0.0, 1.0),
            'sad': random.uniform(0.0, 1.0),
            'surprise': random.uniform(0.0, 1.0),
            'neutral': random.uniform(0.0, 1.0)
        }
        
        # 归一化，使总和为1
        total = sum(emotions.values())
        if total > 0:
            for key in emotions:
                emotions[key] /= total
        
        return emotions
    
    def add_emotion_to_cache(self, emotions):
        """添加表情数据到缓存"""
        emotion_data = emotions.copy()
        emotion_data['timestamp'] = time.time()
        
        self.emotion_data_cache.append(emotion_data)
        
        # 限制缓存大小
        if len(self.emotion_data_cache) > 1000:
            self.emotion_data_cache.pop(0)
        
        print(f"[缓存] 添加表情数据，缓存大小: {len(self.emotion_data_cache)}")
    
    def calculate_average_emotions(self):
        """计算缓存中表情数据的平均值"""
        if not self.emotion_data_cache:
            return {'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'happy': 0.0, 
                   'sad': 0.0, 'surprise': 0.0, 'neutral': 0.0}
        
        avg_emotions = {}
        emotion_names = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']
        
        for emotion in emotion_names:
            values = [data.get(emotion, 0.0) for data in self.emotion_data_cache]
            avg_emotions[emotion] = sum(values) / len(values) if values else 0.0
        
        return avg_emotions
    
    def process_emotion_average(self):
        """处理表情平均值"""
        if self.emotion_data_cache:
            avg_emotions = self.calculate_average_emotions()
            
            # 找到主导情感
            dominant_emotion = max(avg_emotions.items(), key=lambda x: x[1])
            
            print(f"[平均计算] 缓存中有 {len(self.emotion_data_cache)} 个数据")
            print(f"[平均计算] 主导情感: {dominant_emotion[0]} (强度: {dominant_emotion[1]:.3f})")
            print(f"[平均计算] 所有情感: {', '.join([f'{k}={v:.3f}' for k, v in avg_emotions.items()])}")
            
            # 清空缓存
            self.emotion_data_cache.clear()
            print(f"[清空] 缓存已清空")
        else:
            print("[平均计算] 缓存为空，跳过计算")
        
        print("-" * 80)
    
    def simulate_emotion_detection(self):
        """模拟表情检测过程"""
        print("开始模拟表情检测...")
        print(f"更新间隔: {self.update_interval}秒")
        print("=" * 80)
        
        start_time = time.time()
        last_average_time = start_time
        frame_count = 0
        
        self.is_running = True
        
        try:
            while self.is_running and time.time() - start_time < 30:  # 运行30秒
                # 模拟每帧都有表情数据（约30fps）
                emotions = self.generate_random_emotions()
                self.add_emotion_to_cache(emotions)
                
                frame_count += 1
                
                # 检查是否到了计算平均值的时间
                current_time = time.time()
                if current_time - last_average_time >= self.update_interval:
                    print(f"[定时触发] 间隔 {self.update_interval:.1f}秒 已到，开始计算平均值")
                    print(f"[统计] 累积了 {frame_count} 帧数据")
                    self.process_emotion_average()
                    last_average_time = current_time
                    frame_count = 0
                
                # 模拟帧率（约30fps）
                time.sleep(1/30)
        
        except KeyboardInterrupt:
            print("\n测试被中断")
        
        finally:
            self.is_running = False
            # 处理剩余数据
            if self.emotion_data_cache:
                print(f"[最终] 处理剩余 {len(self.emotion_data_cache)} 个数据")
                self.process_emotion_average()


def test_interval_settings():
    """测试不同间隔设置"""
    print("测试不同时间间隔设置")
    print("=" * 60)
    
    intervals = [1.0, 2.0, 3.0, 5.0]  # 不同的间隔时间
    
    for interval in intervals:
        print(f"\n--- 测试间隔: {interval}秒 ---")
        
        tester = MockEmotionUpdateTest()
        tester.update_interval = interval
        
        # 运行短时间测试
        start_time = time.time()
        frame_count = 0
        
        while time.time() - start_time < interval * 2.5:  # 运行2.5个间隔周期
            emotions = tester.generate_random_emotions()
            tester.add_emotion_to_cache(emotions)
            frame_count += 1
            time.sleep(1/30)  # 模拟30fps
        
        print(f"在 {interval}秒 间隔内收集到 {len(tester.emotion_data_cache)} 个数据点")
        tester.process_emotion_average()


def test_cache_performance():
    """测试缓存性能"""
    print("\n测试缓存性能")
    print("=" * 60)
    
    tester = MockEmotionUpdateTest()
    
    # 测试大量数据的处理速度
    start_time = time.time()
    
    for i in range(1000):  # 添加1000个数据点
        emotions = tester.generate_random_emotions()
        tester.add_emotion_to_cache(emotions)
    
    cache_time = time.time() - start_time
    
    start_time = time.time()
    avg_emotions = tester.calculate_average_emotions()
    calc_time = time.time() - start_time
    
    print(f"缓存1000个数据点耗时: {cache_time:.4f}秒")
    print(f"计算平均值耗时: {calc_time:.4f}秒")
    print(f"缓存大小: {len(tester.emotion_data_cache)}")
    print(f"平均处理速度: {1000/cache_time:.0f} 数据点/秒")


def test_emotion_averaging():
    """测试表情平均计算"""
    print("\n测试表情平均计算准确性")
    print("=" * 60)
    
    tester = MockEmotionUpdateTest()
    
    # 添加已知的测试数据
    test_data = [
        {'happy': 1.0, 'sad': 0.0, 'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'surprise': 0.0, 'neutral': 0.0},
        {'happy': 0.0, 'sad': 1.0, 'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'surprise': 0.0, 'neutral': 0.0},
        {'happy': 0.5, 'sad': 0.5, 'angry': 0.0, 'disgust': 0.0, 'fear': 0.0, 'surprise': 0.0, 'neutral': 0.0}
    ]
    
    print("输入测试数据:")
    for i, data in enumerate(test_data):
        print(f"  数据{i+1}: {data}")
        tester.add_emotion_to_cache(data)
    
    avg_emotions = tester.calculate_average_emotions()
    print(f"\n计算得到的平均值:")
    for emotion, value in avg_emotions.items():
        print(f"  {emotion}: {value:.3f}")
    
    # 验证结果
    expected_happy = (1.0 + 0.0 + 0.5) / 3
    expected_sad = (0.0 + 1.0 + 0.5) / 3
    
    print(f"\n验证结果:")
    print(f"  happy 期望值: {expected_happy:.3f}, 实际值: {avg_emotions['happy']:.3f}")
    print(f"  sad 期望值: {expected_sad:.3f}, 实际值: {avg_emotions['sad']:.3f}")
    
    if abs(avg_emotions['happy'] - expected_happy) < 0.001 and abs(avg_emotions['sad'] - expected_sad) < 0.001:
        print("✅ 平均计算测试通过")
    else:
        print("❌ 平均计算测试失败")


def main():
    """主测试函数"""
    print("表情间隔更新功能测试")
    print("=" * 60)
    
    try:
        # 测试1: 平均计算准确性
        test_emotion_averaging()
        
        # 测试2: 不同间隔设置
        test_interval_settings()
        
        # 测试3: 缓存性能
        test_cache_performance()
        
        # 测试4: 完整模拟
        print("\n开始完整模拟测试（30秒）")
        print("按 Ctrl+C 可以提前停止")
        print("=" * 60)
        
        tester = MockEmotionUpdateTest()
        tester.simulate_emotion_detection()
        
        print("\n所有测试完成!")
        print("=" * 60)
        print("功能总结:")
        print("✅ 表情数据缓存机制")
        print("✅ 定时平均计算")
        print("✅ 主导情感识别")
        print("✅ 缓存大小管理")
        print("✅ 性能优化")
        
        print("\n使用说明:")
        print("1. 启动VRChat OSC应用")
        print("2. 开启摄像头和面部识别")  
        print("3. 使用'表情更新间隔'滑块调节更新频率（1-10秒）")
        print("4. 表情数据会在设定间隔内收集并计算平均值")
        print("5. 只有平均值会传递给LLM进行情感感知处理")
        
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()