import os
import json
from typing import List, Dict, Any

def merge_json_files_to_jsonp(directory: str, output_file: str, callback_name: str) -> None:
    merged_data: List[Dict[str, Any]] = []

    # 遍历目录中的所有文件
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            file_path = os.path.join(directory, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    merged_data.extend(data)
                elif isinstance(data, dict):
                    merged_data.append(data)

    # 将合并后的数据写入 JSONP 文件
    with open(output_file, 'w', encoding='utf-8') as f:
        jsonp_content = f"{callback_name}({json.dumps(merged_data, ensure_ascii=False)})\n"
        f.write(jsonp_content)

# 使用示例
directory_path = 'storage\datasets\JGDY_Crawl_Detail'
output_jsonp_file = 'merged_output.jsonp'
callback_function_name = 'callback'

merge_json_files_to_jsonp(directory_path, output_jsonp_file, callback_function_name)