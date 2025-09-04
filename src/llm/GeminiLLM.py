#!/usr/bin/env python3
"""
Gemini LLM客户端 - 对接Google Gemini API
"""

import requests
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class GeminiResponse:
    """Gemini响应数据类"""
    text: str
    usage_metadata: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    error: Optional[str] = None


class GeminiClient:
    """Gemini LLM客户端类"""
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", config=None):
        """
        初始化Gemini客户端
        
        Args:
            api_key: Gemini API密钥
            model: 使用的模型名称
            config: 配置管理器实例
        """
        self.api_key = api_key
        self.model = model
        self.config = config
        
        # API端点
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        
        # 请求配置
        self.timeout = 30
        self.max_retries = 3
        self.retry_delay = 1.0
        
        # 模型参数
        self.generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
        print(f"✅ Gemini客户端初始化完成 (模型: {self.model})")
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        发送HTTP请求到Gemini API
        
        Args:
            endpoint: API端点
            data: 请求数据
            
        Returns:
            API响应数据或None
        """
        url = f"{self.base_url}/{endpoint}?key={self.api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        
        for attempt in range(self.max_retries):
            try:
                print(f"🌐 发送请求到Gemini API (尝试 {attempt + 1}/{self.max_retries})")
                
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    # 速率限制，等待后重试
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"⚠️ 请求频率限制，等待 {wait_time:.1f} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', '未知错误')
                        print(f"❌ 请求参数错误: {error_msg}")
                        return {"error": f"请求参数错误: {error_msg}"}
                    except:
                        print(f"❌ 请求参数错误: {response.text}")
                        return {"error": f"请求参数错误: {response.status_code}"}
                elif response.status_code == 403:
                    print("❌ API密钥无效或权限不足")
                    return {"error": "API密钥无效或权限不足"}
                else:
                    print(f"❌ API请求失败: HTTP {response.status_code}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    return {"error": f"API请求失败: HTTP {response.status_code}"}
                    
            except requests.exceptions.Timeout:
                print(f"⏱️ 请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return {"error": "请求超时"}
                
            except requests.exceptions.ConnectionError:
                print(f"🌐 网络连接错误 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * 2)  # 连接错误等待更久
                    continue
                return {"error": "网络连接错误"}
                
            except Exception as e:
                print(f"❌ 请求异常: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return {"error": f"请求异常: {str(e)}"}
        
        return {"error": "所有重试均失败"}
    
    def generate_content(self, prompt: str, system_prompt: Optional[str] = None) -> GeminiResponse:
        """
        生成内容
        
        Args:
            prompt: 用户输入的提示词
            system_prompt: 系统提示词（可选）
            
        Returns:
            GeminiResponse对象
        """
        try:
            print(f"🤖 处理Gemini请求: {prompt[:50]}...")
            
            # 构建消息内容
            contents = []
            
            # 如果有系统提示词，先添加
            if system_prompt:
                contents.append({
                    "role": "user",
                    "parts": [{"text": f"System: {system_prompt}"}]
                })
            
            # 添加用户消息
            contents.append({
                "role": "user", 
                "parts": [{"text": prompt}]
            })
            
            # 构建请求数据
            request_data = {
                "contents": contents,
                "generationConfig": self.generation_config,
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    }
                ]
            }
            
            # 发送请求
            endpoint = f"models/{self.model}:generateContent"
            response_data = self._make_request(endpoint, request_data)
            
            if not response_data:
                return GeminiResponse(
                    text="",
                    error="无法连接到Gemini API"
                )
            
            # 检查错误
            if "error" in response_data:
                return GeminiResponse(
                    text="",
                    error=response_data["error"]
                )
            
            # 解析响应
            candidates = response_data.get("candidates", [])
            if not candidates:
                return GeminiResponse(
                    text="",
                    error="API返回空响应"
                )
            
            candidate = candidates[0]
            
            # 检查完成原因
            finish_reason = candidate.get("finishReason", "")
            if finish_reason == "SAFETY":
                return GeminiResponse(
                    text="",
                    error="内容被安全过滤器阻止",
                    finish_reason=finish_reason
                )
            elif finish_reason == "RECITATION":
                return GeminiResponse(
                    text="",
                    error="内容可能涉及版权问题",
                    finish_reason=finish_reason
                )
            
            # 提取文本内容
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                return GeminiResponse(
                    text="",
                    error="响应中没有找到文本内容"
                )
            
            # 合并所有文本部分
            text_parts = []
            for part in parts:
                if "text" in part:
                    text_parts.append(part["text"])
            
            response_text = "".join(text_parts).strip()
            
            # 提取使用情况元数据
            usage_metadata = response_data.get("usageMetadata", {})
            
            print(f"✅ Gemini响应成功，文本长度: {len(response_text)}")
            
            return GeminiResponse(
                text=response_text,
                usage_metadata=usage_metadata,
                finish_reason=finish_reason
            )
            
        except Exception as e:
            print(f"❌ Gemini内容生成失败: {e}")
            import traceback
            traceback.print_exc()
            return GeminiResponse(
                text="",
                error=f"内容生成异常: {str(e)}"
            )
    
    def chat(self, message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> GeminiResponse:
        """
        进行对话
        
        Args:
            message: 用户消息
            conversation_history: 对话历史 [{"role": "user/model", "text": "..."}]
            
        Returns:
            GeminiResponse对象
        """
        try:
            print(f"💬 处理对话请求: {message[:50]}...")
            
            # 构建对话内容
            contents = []
            
            # 添加历史对话
            if conversation_history:
                for msg in conversation_history:
                    role = msg["role"]
                    # Gemini API中助手角色是"model"
                    if role == "assistant":
                        role = "model"
                    
                    contents.append({
                        "role": role,
                        "parts": [{"text": msg["text"]}]
                    })
            
            # 添加当前用户消息
            contents.append({
                "role": "user",
                "parts": [{"text": message}]
            })
            
            # 构建请求数据
            request_data = {
                "contents": contents,
                "generationConfig": self.generation_config
            }
            
            # 发送请求
            endpoint = f"models/{self.model}:generateContent"
            response_data = self._make_request(endpoint, request_data)
            
            if not response_data:
                return GeminiResponse(
                    text="",
                    error="无法连接到Gemini API"
                )
            
            # 检查错误
            if "error" in response_data:
                return GeminiResponse(
                    text="",
                    error=response_data["error"]
                )
            
            # 解析响应（与generate_content相同的逻辑）
            candidates = response_data.get("candidates", [])
            if not candidates:
                return GeminiResponse(
                    text="",
                    error="API返回空响应"
                )
            
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            
            if not parts:
                return GeminiResponse(
                    text="",
                    error="响应中没有找到文本内容"
                )
            
            # 合并文本内容
            text_parts = [part["text"] for part in parts if "text" in part]
            response_text = "".join(text_parts).strip()
            
            # 提取元数据
            usage_metadata = response_data.get("usageMetadata", {})
            finish_reason = candidate.get("finishReason", "")
            
            print(f"✅ 对话响应成功，文本长度: {len(response_text)}")
            
            return GeminiResponse(
                text=response_text,
                usage_metadata=usage_metadata,
                finish_reason=finish_reason
            )
            
        except Exception as e:
            print(f"❌ 对话处理失败: {e}")
            import traceback
            traceback.print_exc()
            return GeminiResponse(
                text="",
                error=f"对话处理异常: {str(e)}"
            )
    
    def set_generation_config(self, **kwargs):
        """
        设置生成配置
        
        Args:
            temperature: 温度参数 (0.0-1.0)
            top_p: Top-p参数 (0.0-1.0)  
            top_k: Top-k参数
            max_output_tokens: 最大输出长度
        """
        for key, value in kwargs.items():
            if key in self.generation_config:
                self.generation_config[key] = value
                print(f"🔧 更新生成参数: {key} = {value}")
    
    def test_connection(self) -> bool:
        """
        测试API连接
        
        Returns:
            连接是否成功
        """
        try:
            print("🔍 测试Gemini API连接...")
            
            test_prompt = "请简单回答：你好"
            response = self.generate_content(test_prompt)
            
            if response.error:
                print(f"❌ 连接测试失败: {response.error}")
                return False
            
            if response.text:
                print(f"✅ 连接测试成功，响应: {response.text[:50]}...")
                return True
            else:
                print("❌ 连接测试失败: 空响应")
                return False
                
        except Exception as e:
            print(f"❌ 连接测试异常: {e}")
            return False