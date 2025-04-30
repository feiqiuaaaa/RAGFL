import json
import os
import re

import code_block as block


def _format_solidity_blank_lines(code):
    lines = code.split('\n')
    formatted = []

    # 状态跟踪变量
    prev_is_function = False  # 前一行是否是函数定义
    pending_empty_line = False  # 等待处理的空行标记

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 判断行类型
        is_function = re.match(r'^(function|constructor|event)', stripped) is not None
        is_empty = stripped == ''

        # 函数定义处理逻辑
        if is_function:
            if prev_is_function:
                # 函数之间保留一个空行
                _add_conditional_empty(formatted, require_empty=True)
            formatted.append(line)
            pending_empty_line = False
            prev_is_function = True
            continue

        # 空行处理逻辑
        if is_empty:
            if not pending_empty_line:
                pending_empty_line = True
            continue

        # 普通代码行处理
        if pending_empty_line:
            _add_conditional_empty(formatted)
            pending_empty_line = False
        formatted.append(line)
        prev_is_function = False

    # 处理最后一个等待中的空行
    if pending_empty_line:
        _add_conditional_empty(formatted)

    # 最终合并连续空行
    return _merge_blank_lines('\n'.join(formatted))


def format_solidity_blank_lines(code):
    lines = code.split('\n')
    formatted = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        # 空行处理逻辑
        if stripped == '':
            continue
        formatted.append(line)
    # 最终合并连续空行
    return _merge_blank_lines('\n'.join(formatted))


def _add_conditional_empty(lines, require_empty=False):
    """智能添加空行，避免连续空行"""
    if require_empty or (lines and lines[-1].strip() != ''):
        if lines and lines[-1] == '':
            return
        lines.append('')


def _merge_blank_lines(code):
    """合并多个连续空行为单个空行"""
    return re.sub(r'\n{3,}', '\n\n', code).strip() + '\n'


def full_clean_solidity(codes: {}):
    for key in codes.keys():
        code = codes[key]['code']
        # 移除 UTF-8 BOM 头
        # code = code.lstrip('\ufeff')
        # 替换中文标点
        code = code.translate(str.maketrans({
            '‘': "'", '’': "'", '“': '"', '”': '"',
            '。': '.', '，': ',', '；': ';', '：': ':'
        }))
        # 统一换行符
        # code = code.replace('\r\n', '\n').replace('\r', '\n')
        # 调用空行格式化
        # formatted_code = format_solidity_blank_lines(code)
        codes[key]['code'] = code
    return codes


def get_sol_name(sol_path: str) -> str:
    parts = [part for part in sol_path.split('/') if part]
    return parts[-1] if parts else ''


def save_contract_from_json(save_path: str, file_name: str, file_content: str):
    with open(save_path + file_name, 'w', encoding='utf-8') as f:
        f.write(file_content)
        f.close()


def read_response_json(json_data: json, file_name: str) -> {}:
    # 存储结果的字典
    contracts = {}

    # 创建保存合约代码文件夹
    save_path = 'source_code/detail/'
    direct = os.path.join(save_path, file_name)
    if not os.path.exists(direct):
        os.mkdir(direct)
    code_save_path = save_path + file_name + '/'

    # 遍历所有源文件
    for file_name, file_info in json_data.items():
        # 取sol文件名
        sol_name = get_sol_name(file_name)
        content = file_info.get('content', '')
        contracts[file_name] = {'code': content, 'sol_name': sol_name}
        save_contract_from_json(code_save_path, sol_name, content)

    return contracts


def direct_read_code(raw_path: str, names: list):
    for name in names:
        path = raw_path + name
        if not os.path.exists(path):
            raise FileNotFoundError(f"路径不存在: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 文档获取 + 清洗
            code_dic = read_response_json(data['sources'], name)
            formatted_code_dic = full_clean_solidity(code_dic)
            # 文档分块
            block.extract_source_code_slices(formatted_code_dic, path.split('/')[-1])

