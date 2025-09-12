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
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", config=None):
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
            # 移除 max_output_tokens 限制，让 API 返回完整内容
            # "max_output_tokens": 20480,
        }
        
        print(f"[成功] Gemini客户端初始化完成 (模型: {self.model})")
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        发送HTTP请求到Gemini API
        
        Args:
            endpoint: API端点
            data: 请求数据
            
        Returns:
            API响应数据或None
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key
        }
        
        for attempt in range(self.max_retries):
            try:
                # print(f"[网络] 发送请求到Gemini API (尝试 {attempt + 1}/{self.max_retries})")
                # print(f"[调试] URL: {url}")
                # print(f"[调试] Headers: {headers}")
                # print(f"[调试] Data: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
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
                    print(f"[警告] 请求频率限制，等待 {wait_time:.1f} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', '未知错误')
                        print(f"[错误] 请求参数错误: {error_msg}")
                        return {"error": f"请求参数错误: {error_msg}"}
                    except:
                        print(f"[错误] 请求参数错误: {response.text}")
                        return {"error": f"请求参数错误: {response.status_code}"}
                elif response.status_code == 403:
                    print("[错误] API密钥无效或权限不足")
                    return {"error": "API密钥无效或权限不足"}
                else:
                    print(f"[错误] API请求失败: HTTP {response.status_code}")
                    print(f"[错误] 请求URL: {url}")
                    print(f"[错误] 响应内容: {response.text}")
                    print(f"[错误] 响应头: {dict(response.headers)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    return {"error": f"API请求失败: HTTP {response.status_code} - {response.text}"}
                    
            except requests.exceptions.Timeout:
                print(f"[时间] 请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return {"error": "请求超时"}
                
            except requests.exceptions.ConnectionError:
                print(f"[网络] 网络连接错误 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * 2)  # 连接错误等待更久
                    continue
                return {"error": "网络连接错误"}
                
            except Exception as e:
                print(f"[错误] 请求异常: {e}")
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
            print(f"[AI] 处理Gemini请求: {prompt[:50]}...")
            
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
            
            print(f"[成功] Gemini响应成功，文本长度: {len(response_text)}")
            
            return GeminiResponse(
                text=response_text,
                usage_metadata=usage_metadata,
                finish_reason=finish_reason
            )
            
        except Exception as e:
            print(f"[错误] Gemini内容生成失败: {e}")
            import traceback
            traceback.print_exc()
            return GeminiResponse(
                text="",
                error=f"内容生成异常: {str(e)}"
            )
    
    def generate_content_stream(self, prompt: str, system_prompt: Optional[str] = None, 
                               conversation_history: Optional[List[Dict[str, str]]] = None, callback=None):
        """
        流式生成内容
        
        Args:
            prompt: 用户输入的提示词
            system_prompt: 系统提示词（可选）
            conversation_history: 对话历史 [{"role": "user/assistant", "text": "..."}]
            callback: 回调函数，接收每个流式片段 callback(chunk_text, is_final)
            
        Returns:
            完整的文本响应
        """
        try:
            print(f"[AI流式] 处理Gemini流式请求: {prompt[:50]}...")
            
            # 构建消息内容
            contents = []
            
            # 如果有系统提示词，先添加
            if system_prompt:
                contents.append({
                    "role": "user",
                    "parts": [{"text": f"System: {system_prompt}"}]
                })
            
            # 添加对话历史
            if conversation_history:
                print(f"[对话历史] 加载 {len(conversation_history)} 条历史记录")
                for msg in conversation_history:
                    role_map = {
                        "user": "user",
                        "assistant": "model",  # Gemini 使用 "model" 作为助手角色
                        "model": "model"
                    }
                    gemini_role = role_map.get(msg.get("role"), "user")
                    contents.append({
                        "role": gemini_role,
                        "parts": [{"text": msg.get("text", "")}]
                    })
            else:
                print("[对话历史] 无历史记录，新对话开始")
            
            # 添加当前用户消息
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
            
            # 使用流式端点
            endpoint = f"models/{self.model}:streamGenerateContent"
            full_response = self._make_streaming_request(endpoint, request_data, callback)
            
            return full_response
            
        except Exception as e:
            print(f"[错误] Gemini流式内容生成失败: {e}")
            import traceback
            traceback.print_exc()
            if callback:
                callback("", True)  # 标记结束
            return ""
    
    def _make_streaming_request(self, endpoint: str, data: Dict[str, Any], callback=None) -> str:
        """
        发送流式请求到Gemini API
        
        Args:
            endpoint: API端点
            data: 请求数据
            callback: 流式回调函数
            
        Returns:
            完整响应文本
        """
        try:
            url = f"{self.base_url}/{endpoint}?key={self.api_key}"
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            print(f"[流式请求] 发送到: {url}")
            
            # 发送流式请求
            response = requests.post(
                url, 
                json=data, 
                headers=headers, 
                stream=True,  # 启用流式响应
                timeout=60
            )
            
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                print(f"[错误] API请求失败: {error_msg}")
                if callback:
                    callback("", True)
                return ""
            
            full_text = ""
            chunk_count = 0
            raw_data = ""
            
            print("[流式响应] 开始接收数据流...")
            
            # 收集所有响应数据
            line_count = 0
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    raw_data += line
                    line_count += 1
                    if line_count <= 3:  # 只打印前3行用于调试
                        print(f"[流式数据] 第{line_count}行: {line[:200]}...")
            
            print(f"[流式数据] 总共收到 {line_count} 行，数据长度: {len(raw_data)}")
            if len(raw_data) > 200:
                print(f"[流式数据] 前200字符: {raw_data[:200]}")
            else:
                print(f"[流式数据] 完整数据: {raw_data}")
            
            # 尝试解析完整的JSON响应
            try:
                # 先尝试作为完整JSON解析
                response_data = json.loads(raw_data)
                print(f"[调试] 响应数据类型: {type(response_data)}")
                
                # 处理不同的响应格式
                all_candidates = []
                if isinstance(response_data, list):
                    print(f"[调试] 数组响应，长度: {len(response_data)}")
                    # 如果响应是数组格式，需要处理所有元素，它们是流式片段
                    for i, item in enumerate(response_data):
                        if isinstance(item, dict):
                            item_candidates = item.get("candidates", [])
                            all_candidates.extend(item_candidates)
                            print(f"[调试] 从数组[{i}]获取到 {len(item_candidates)} 个候选")
                    print(f"[调试] 总共收集到 {len(all_candidates)} 个候选")
                elif isinstance(response_data, dict):
                    print("[调试] 字典响应格式")
                    # 如果响应是对象格式
                    all_candidates = response_data.get("candidates", [])
                    print(f"[调试] 从字典获取到 {len(all_candidates)} 个候选")
                
                if all_candidates:
                    # 合并所有候选的文本内容
                    for candidate in all_candidates:
                        content = candidate.get("content", {})
                        parts = content.get("parts", [])
                        
                        # 提取所有文本内容
                        for part in parts:
                            if "text" in part:
                                full_text += part["text"]
                    
                    if full_text:
                        chunk_count = 1
                        print(f"[完整响应] 收到: {len(full_text)} 字符")
                        
                        # 调用回调函数传递完整响应
                        if callback:
                            # 对于数组响应，我们逐个处理各个片段，然后发送最终完整响应
                            if isinstance(response_data, list) and len(response_data) > 1:
                                # 如果是多个片段，先逐个发送，再发送最终完成信号
                                accumulated_text = ""
                                for i, item in enumerate(response_data):
                                    if isinstance(item, dict):
                                        item_candidates = item.get("candidates", [])
                                        item_text = ""
                                        for candidate in item_candidates:
                                            content = candidate.get("content", {})
                                            parts = content.get("parts", [])
                                            for part in parts:
                                                if "text" in part:
                                                    item_text += part["text"]
                                        
                                        if item_text:
                                            accumulated_text += item_text
                                            is_final = (i == len(response_data) - 1)
                                            print(f"[流式片段 {i+1}/{len(response_data)}] 发送: {len(item_text)} 字符, is_final: {is_final}")
                                            callback(item_text, is_final)
                            else:
                                # 单个响应，直接发送完整内容
                                callback(full_text, True)
                        
                        # 如果是完整响应模式，跳过逐行解析
                        print(f"[流式结束] 完整响应模式，总文本长度: {len(full_text)}")
                        return full_text
                    
                    # 检查所有候选的完成状态
                    for candidate in all_candidates:
                        finish_reason = candidate.get("finishReason", "")
                        if finish_reason:
                            print(f"[响应完成] 原因: {finish_reason}")
                            if finish_reason == "LENGTH":
                                print("[警告] 响应因长度限制被截断")
                            elif finish_reason == "SAFETY":
                                print("[警告] 响应被安全过滤器阻止")
                            elif finish_reason == "RECITATION":
                                print("[警告] 响应因版权问题被阻止")
                            break  # 只需要检查第一个有完成状态的候选
                        
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                # 如果不是完整JSON，尝试逐行解析（兼容真正的流式响应）
                lines = raw_data.strip().split('\n')
                for line in lines:
                    if not line.strip():
                        continue
                    
                    try:
                        chunk_data = json.loads(line)
                        chunk_count += 1
                        
                        # 解析流式数据
                        candidates = chunk_data.get("candidates", [])
                        if not candidates:
                            continue
                        
                        candidate = candidates[0]
                        content = candidate.get("content", {})
                        parts = content.get("parts", [])
                        
                        if not parts:
                            continue
                        
                        # 提取文本内容
                        chunk_text = ""
                        for part in parts:
                            if "text" in part:
                                chunk_text += part["text"]
                        
                        if chunk_text:
                            full_text += chunk_text
                            print(f"[流式片段 #{chunk_count}] 收到: {len(chunk_text)} 字符")
                            
                            # 调用回调函数传递流式片段
                            if callback:
                                is_final = candidate.get("finishReason") is not None
                                callback(chunk_text, is_final)
                        
                        # 检查是否完成
                        finish_reason = candidate.get("finishReason", "")
                        if finish_reason:
                            print(f"[流式完成] 原因: {finish_reason}")
                            if finish_reason == "LENGTH":
                                print("[警告] 流式响应因长度限制被截断")
                            elif finish_reason == "SAFETY":
                                print("[警告] 流式响应被安全过滤器阻止")
                            elif finish_reason == "RECITATION":
                                print("[警告] 流式响应因版权问题被阻止")
                            break
                            
                    except json.JSONDecodeError as e:
                        print(f"[警告] 跳过无效JSON行: {line[:100]}")
                        continue
                    except Exception as e:
                        print(f"[警告] 处理流式片段时出错: {e}")
                        continue
            
            print(f"[流式结束] 总共接收 {chunk_count} 个片段，文本长度: {len(full_text)}")
            
            # 只在真正的流式模式下发送结束信号
            if chunk_count > 1 and callback:
                print("[流式模式] 发送最终完成信号")
                callback("", True)
            
            return full_text
            
        except Exception as e:
            print(f"[错误] 流式请求失败: {e}")
            if callback:
                callback("", True)
            return ""
    
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
            
            print(f"[成功] 对话响应成功，文本长度: {len(response_text)}")
            
            return GeminiResponse(
                text=response_text,
                usage_metadata=usage_metadata,
                finish_reason=finish_reason
            )
            
        except Exception as e:
            print(f"[错误] 对话处理失败: {e}")
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
            max_output_tokens: 最大输出长度 (None表示无限制)
        """
        for key, value in kwargs.items():
            if key == "max_output_tokens":
                # 特殊处理max_output_tokens
                if value is None or value <= 0:
                    # 移除限制
                    if key in self.generation_config:
                        del self.generation_config[key]
                    print(f"[更新] 移除输出长度限制")
                else:
                    self.generation_config[key] = value
                    print(f"[更新] 设置最大输出长度: {value}")
            elif key in self.generation_config or key == "max_output_tokens":
                self.generation_config[key] = value
                print(f"[更新] 更新生成参数: {key} = {value}")
    
    def test_connection(self) -> bool:
        """
        测试API连接
        
        Returns:
            连接是否成功
        """
        try:
            print("[搜索] 测试Gemini API连接...")
            
            test_prompt = "请简单回答：你好"
            response = self.generate_content(test_prompt)
            
            if response.error:
                print(f"[错误] 连接测试失败: {response.error}")
                return False
            
            if response.text:
                print(f"[成功] 连接测试成功，响应: {response.text[:50]}...")
                return True
            else:
                print("[错误] 连接测试失败: 空响应")
                return False
                
        except Exception as e:
            print(f"[错误] 连接测试异常: {e}")
            return False