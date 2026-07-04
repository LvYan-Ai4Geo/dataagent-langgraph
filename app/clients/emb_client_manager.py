"""
Embedding 客户端管理器。

封装 HuggingFaceEmbeddings（BGE 本地模型）的初始化，以模块级单例 `emb_client` 暴露。
用于将关键词/字段名/指标名等文本编码为向量，供 Qdrant 向量检索使用。

注意：当前实现中模型路径为硬编码的本地绝对路径，部署到其他环境时需修改
local_model_path（建议改为从 conf/path_config.py 的 BGE_MODEL 读取）。
"""
from langchain_huggingface import HuggingFaceEndpointEmbeddings, HuggingFaceEmbeddings
from app.app_config.config import EmbeddingConfig, object_config

from langchain_huggingface import HuggingFaceEmbeddings
from app.app_config.config import EmbeddingConfig, object_config


class EmbeddingClient:
    def __init__(self, config: EmbeddingConfig):
        self.client: HuggingFaceEmbeddings | None = None
        self.config: EmbeddingConfig = config

    def init(self):
        # 1. 替换为你的 bge 模型在 Docker 内部的真实绝对路径
        local_model_path = 'G:/PythonProject/data-agent/docker/embedding/bge-large-zh-v1.5'

        # 2. 直接使用 HuggingFaceEmbeddings 加载本地模型
        self.client = HuggingFaceEmbeddings(
            model_name=local_model_path,
            # 如果你的 Docker 支持 GPU，可以把 'cpu' 换成 'cuda'
            model_kwargs={'device': 'cpu'},
            # BGE 模型官方强烈建议开启 normalize_embeddings 才能计算准确的余弦相似度
            encode_kwargs={'normalize_embeddings': True}
        )


# 模块级单例
emb_client = EmbeddingClient(config=object_config.embedding)

if __name__ == '__main__':
    # 连通性自测：编码中文/英文文本并打印向量维度与前几个值
    emb_client.init()


    def test():
        client = emb_client.client
        text = "什么是深度学习？"

        result = client.embed_query(text)
        print(f"向量维度: {len(result)}")
        print(f"前3个值: {result[:3]}")


    test()

if __name__ == '__main__':
    emb_client.init()

    def test():
        client = emb_client.client

        text = "What is deep learning?"

        result = client.embed_query(text)

        print(result[:3])

    test()
