"""
Prompt 模板加载器。

所有 LLM 提示词以 `.prompt` 文件形式集中存放在项目根目录的 prompts/ 目录下，
便于独立维护与版本管理。本模块提供 load_prompt(name) 按名称读取对应模板文本。
"""
from pathlib import Path


def load_prompt(name:str):
    """
    根据名称加载 prompt 模板文件。

    :param name: 模板名称（不含扩展名），例如 "generate_sql"
    :return: 模板文件的纯文本内容
    路径推算：本文件位于 app/agent/prompt/prompt_loader.py，
    向上回溯 3 级到项目根目录，再进入 prompts/ 目录。
    """
    file_path = Path(__file__).parents[3] / 'prompts' / f'{name}.prompt'
    return file_path.read_text(encoding='utf-8')
