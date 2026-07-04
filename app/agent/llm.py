"""
LLM 客户端初始化模块。

从 .env 加载环境变量（如 DEEPSEEK_API_KEY），并基于应用配置
（app_config.yaml 中的 llm 段）通过 langchain 的 init_chat_model
初始化一个 DeepSeek Chat 模型实例。该实例以模块级单例 `llm` 暴露，
供各节点构造 chain 时复用。
"""
from langchain.chat_models import init_chat_model
from app.app_config.config import object_config
from dotenv import load_dotenv

# 加载项目根目录下 .env 中的环境变量（用于注入 LLM API Key 等敏感信息）
load_dotenv()

# 初始化 DeepSeek Chat 模型单例：
#   - model_name / base_url 来自 app_config.yaml
#   - temperature=0.1 降低随机性，提升 SQL 生成与修正的稳定性
llm = init_chat_model(model=object_config.llm.model_name,
                      model_provider='deepseek',
                      base_url=object_config.llm.base_url,
                      temperature=0.1)

if __name__ == '__main__':
    # 简单连通性自测
    print(llm.invoke('你是谁').content)
