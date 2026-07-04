"""
路径常量配置。

集中定义项目中的关键路径，避免在代码中硬编码绝对路径。
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent                      # 项目根目录
BGE_MODEL = ROOT / 'docker' / 'embedding' / 'bge-large-zh-v1.5'  # BGE 本地模型路径