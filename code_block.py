import json
import re
import subprocess
import uuid

import chromadb
import llm
from complie_contracts.extract_slice_by_ast import parse_ast, src_to_line_numbers
from complie_contracts.test import _load_compile_result


def parse_src(src_str):
    """解析src字符串，返回起始位置和长度"""
    parts = src_str.split(':')
    return int(parts[0]), int(parts[1])


def detect_solc_version(code: str):
    """从Solidity文件中提取pragma版本"""
    # 匹配类似 pragma solidity ^0.8.0; 的声明
    match = re.search(r'pragma solidity\s*([>=^<~]*\s*\d+\.\d+\.\d+);', code)
    if not match:
        return None  # 未找到版本声明

    version = match.group(1).replace('^', '').replace('>=', '').strip()
    return version


def get_installed_versions():
    """获取已安装的 solc 版本列表"""
    try:
        result = subprocess.run(
            ["solc-select", "versions"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # 使用正则匹配版本号 (如 0.8.0, 0.7.6 等)
        versions = re.findall(r"\d+\.\d+\.\d+", result.stdout)
        return set(versions)
    except subprocess.CalledProcessError as e:
        print(f"获取版本失败: {e.stderr}")
        return set()
    except FileNotFoundError:
        print("错误: solc-select 未安装或不在 PATH 中")
        raise


def install_version(version):
    """安装指定版本的 solc 编译器"""
    try:
        print(f"正在安装 solc {version}...")
        subprocess.run(
            ["solc-select", "install", version],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"成功安装 solc {version}")
    except subprocess.CalledProcessError as e:
        print(f"安装失败 (exit code {e.returncode}): {e.stderr}")
        raise
    except FileNotFoundError:
        print("错误: solc-select 未安装或不在 PATH 中")
        raise


def ensure_solc_version(target_version):
    """确保目标编译器版本已安装"""
    try:
        # 获取已安装版本
        installed = get_installed_versions()
        # 检查版本是否存在
        if target_version in installed:
            return True
        # 如果不存在则安装
        install_version(target_version)
        return True
    except Exception as e:
        print(f"操作失败: {str(e)}")
        return False


def switch_solc_version(version: str):
    if ensure_solc_version(version):
        try:
            result = subprocess.run(
                ["solc-select", "use", version],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("Command output:", result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Error executing command (exit code {e.returncode}):")
            print("Error message:", e.stderr)
        except FileNotFoundError:
            print("Error: 'solc-select' not found. Is it installed and in your PATH?")
    else:
        print("solc编译器版本获取失败")


def split_function(content, function_list):
    lines = content.split('\n')
    flag = -1  # 作为二维数组下标使用

    for line in lines:
        text = line.strip()  # 去除两边的空格
        if len(text) > 0:  # 只处理非空行
            parts = text.split()
            if len(parts) > 0 and (parts[0] == "function" or parts[0] == "modifier"):  # or parts[0] == "constructor"
                function_list.append([text])
                flag += 1
            # 将内容添加到当前函数
            elif len(function_list) > 0 and flag >= 0:
                function_list[flag].append(text)

    return function_list


def split_function_by_line(content, start_line, end_line) -> []:
    lines = content.split("\n")
    result = list()
    for i in range(start_line - 1, end_line):
        result.append(lines[i])
    return result


def extract_function_slices(code: str, relative_path: str) -> {}:
    # 寻找绝对路径
    # current_path = os.path.dirname(os.path.abspath(__file__))
    # absolute_path = os.path.join(current_path, relative_path)

    # 调整为限定的编译器版本
    version = detect_solc_version(code)
    switch_solc_version(version)

    # 调用solc生成AST
    result = subprocess.run(
        ['solc', '--standard-json', relative_path],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print("Error generating AST:", result.stderr)
        return []

    # 解析AST JSON
    try:
        ast_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Failed to parse AST JSON.")
        return []

    functions = []

    # 遍历AST中的每个源文件
    for source in ast_data.get('sources', {}).values():
        ast = source.get('AST', {})
        if ast.get('nodeType') != 'SourceUnit':
            continue

        # 遍历AST节点查找合约定义
        for node in ast.get('nodes', []):
            if node.get('nodeType') == 'ContractDefinition':
                # 遍历合约中的函数定义
                for child_node in node.get('nodes', []):
                    if child_node.get('nodeType') == 'FunctionDefinition':
                        src_str = child_node.get('src', '')
                        start, length = parse_src(src_str)
                        # 截取函数代码
                        function_code = source_code[start:start + length].decode('utf-8')
                        functions.append({
                            'name': child_node.get('name', 'unnamed'),
                            'code': function_code.strip()
                        })

    return functions


def extract_function_metadata(function_lists, belong):
    metadata_list = []

    # 正则表达式模式
    func_pattern = re.compile(
        r'(function|modifier)\s+([^(]+)\(([^)]*)\)\s*'  # 函数名和参数
        r'(?:([a-z]+\s+)*)?'  # 可见性和状态可变性
        r'(?:([^{]+))?'  # 修饰符部分
    )
    event_pattern = re.compile(r'emit\s+([\w_]+)\(')
    external_call_patterns = [
        re.compile(r'\.call\('),
        re.compile(r'\.transfer\('),
        re.compile(r'\.send\('),
        re.compile(r'\.delegatecall\(')
    ]

    for block_idx, block in enumerate(function_lists):
        current_func = None

        for line_idx, line in enumerate(block):
            stripped = line.strip()
            # 检测函数开始
            if (stripped.startswith('function') or stripped.startswith('modifier')) and current_func is None:
                current_func = {
                    'def_line': stripped,
                    'body': [],
                    'modifiers': [],
                    'visibility': 'public',
                    'mutability': ''
                }
                # 解析函数定义
                match = func_pattern.search(stripped)
                if match:
                    current_func['name'] = match.group(2).strip()
                    current_func['params'] = match.group(3).strip()
                    modifiers = re.findall(r'\b(public|private|internal|external|pure|view|payable|[\w_]+)\b',
                                           match.group(1))
                    for m in modifiers:
                        if m in ['public', 'private', 'internal', 'external']:
                            current_func['visibility'] = m
                        elif m in ['pure', 'view', 'payable']:
                            current_func['mutability'] = m
                        elif m not in ['function', current_func['name']] and m.strip():
                            current_func['modifiers'].append(m)
            elif current_func is not None:
                # 记录函数体内容
                current_func['body'].append(stripped)

        if current_func is None:
            metadata_list.append({})
            continue

        # 处理收集到的函数
        metadata = {
            "函数名": current_func.get('name', ''),
            "可见性": current_func.get('visibility', 'public'),
            "状态可变性": current_func.get('mutability', 'non-payable'),
            "参数": current_func.get('params', ''),
            "返回值": "",
            "是否包含权限校验逻辑": any('only' in m.lower() for m in current_func['modifiers']) or
                          any('msg.sender' in line for line in current_func['body']),
            "是否使用防重入锁": any('nonReentrant' in m for m in current_func['modifiers']),
            "触发的事件": str(list(set(event_pattern.search(line).group(1)
                                  for line in current_func['body'] if event_pattern.search(line)))),
            "函数所属的合约或接口": belong,  # 需要上下文信息
            "外部调用": any(any(p.search(line) for p in external_call_patterns)
                        for line in current_func['body']),
            "状态变量依赖": '',
            "block索引": block_idx,
        }
        metadata_list.append(metadata)

    return metadata_list


def check_if_fault(fault_list: [], each_address, each_key, each_begin_line, each_end_line, code):
    for fault in fault_list:
        if fault['address'] == each_address and fault['filename'] == each_key:
            fault_begin_char = fault['fault_begin_char']
            fault_offset_char = fault['fault_offset_char']
            fault_begin_line, fault_end_line = src_to_line_numbers(fault_begin_char, fault_offset_char, code)
            if each_begin_line <= fault_begin_line and each_end_line >= fault_end_line:
                return True
    return False


def extract_contract_summary_and_function_slice(codes: {}, dapp_name: str, total_ast, _file, address, fault_list, contract_collection, function_collection):
    for key in codes.keys():  # 对于 dapp 中的每个合约
        code = codes[key]['code']
        sol_name = codes[key]['sol_name']

        # 将合约级概括放入 Contract 集合中
        exists = contract_collection.get(ids=dapp_name + "-" + sol_name)
        if len(exists.get('ids', [])) == 0:
            # LLM 生成概括总结
            system_prompt = llm.load_prompt("prompt/code_summary_system_prompt")
            user_prompt = llm.load_prompt("prompt/code_summary_user_prompt") + code
            summary = llm.get_summary_from_llm(system_prompt, user_prompt)
            if summary[0] != 'stop':
                return summary[0]
            summary = summary[1]

            contract_collection.add(
                documents=[summary],
                ids=[dapp_name + "-" + sol_name],
                metadatas={"address": address}
            )
            _file.write("------------------------------------------------" + "\n合约ID：" + dapp_name + "-" + sol_name + "\n合约总结：\n" + summary)

        # 解析 AST 生成函数元数据 + 函数切片
        # 函数名
        # 可见性
        # 状态可变性
        # 函数参数与返回值
        # 是否包含权限校验逻辑
        # 是否使用防重入锁
        # 触发的事件
        # 可能抛出的 Error 类型
        # 函数所属的合约或接口
        # 外部调用
        # 状态变量依赖（函数读写哪些合约状态变量）
        # 代码位置

        if len(total_ast) == 0:
            _file.write(address + "编译结果 ast 为空\n")
            return
        ast = total_ast[key]
        metadata = parse_ast(ast)
        for index, each in enumerate(metadata):  # 对合约中的每个函数
            if len(each) == 0:
                continue
            start, offset, file_index = map(int, each['src'].split(':'))
            start_line, end_line = src_to_line_numbers(start, offset, codes[key]['code'])
            each['src'] = str(start_line) + "#" + str(end_line)
            each['contract'] = dapp_name + "-" + sol_name
            if check_if_fault(fault_list, address, key, start_line, end_line, code):
                _file.write("\n故障函数！\n")

            final_metadata = {
                "message": str(each),
                "is_fault": check_if_fault(fault_list, address, key, start_line, end_line, code),
                "belong": dapp_name + "-" + sol_name
            }
            # 进行函数切片
            function_slice = split_function_by_line(codes[key]['code'], start_line, end_line)
            function_slice = '\n'.join(function_slice)

            # 生成独立 ID
            function_id = dapp_name + "-" + sol_name + "-" + each['name'] + "-" + str(index)

            # 将函数切片装入 Function 集合中
            exists = function_collection.get(ids=function_id)
            if len(exists.get('ids', [])) == 0:
                function_collection.add(
                    documents=function_slice,
                    metadatas=final_metadata,
                    ids=function_id
                )
                _file.write("------------------------------------------------" + "\n函数ID：" + function_id + "\n函数元数据：\n" + str(
                    final_metadata) + "\n函数切片：\n" + function_slice)

        # if function_list is []:
        #     continue

        # # 进行函数切片
        # function_list = []
        # function_list = split_function(code, function_list)
        # if function_list is []:
        #     continue

        # metadata = extract_function_metadata(function_list, raw_sol + "-" + key)
        # print(json.dumps(metadata, indent=2, ensure_ascii=False))
        # merged_functions = ['\n'.join(sublist) for sublist in function_list]
        # id_list = []
        # for meta_index, meta in enumerate(metadata):
        #     if len(meta) == 0 or meta["函数名"] == "":
        #         id_list.append(raw_sol + "-" + key + "-" + str(meta_index))
        #     else:
        #         id_list.append(raw_sol + "-" + key + "-" + meta["函数名"] + "-" + str(meta_index))
        #
        # # 将函数切片装入 Function 集合中
        # collection = client.get_or_create_collection("Function")
        # for function, meta, fid in zip(merged_functions, metadata, id_list):
        #     exists = collection.get(ids=fid)
        #     if len(exists.get('ids', [])) == 0:
        #         collection.add(
        #             documents=function,
        #             metadatas=meta,
        #             ids=fid
        #         )


if __name__ == '__main__':
    source_code = {"xxx.sol": "xxxxx"}
    path = ""  # JSON 格式sol位置
    extract_contract_summary(source_code, path)
