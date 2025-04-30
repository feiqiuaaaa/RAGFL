import asyncio
import json
import os
import time
import traceback
from json import JSONDecodeError
from typing import Set, Dict
from web3 import Web3
import chromadb
import requests

import settings
from code_clean import read_response_json, full_clean_solidity
from complie_contracts.ContractDao import ContractDao, ContractCompileItem
from complie_contracts.extract_slice_by_ast import parse_ast, src_to_line_numbers
from downloaders.contract import ContractSourceDownloader
from get_source_code import get_contract_address_from_tx
import code_block as block


class CodeHandler:

    def __init__(self, d_path: str, direct_names: list, j_path, json_names):
        self.direct_path = d_path
        self.direct_names = direct_names
        self.json_path = j_path
        self.json_names = json_names
        client = chromadb.PersistentClient(path="./chroma")
        self.contract_collection = client.get_or_create_collection("Contract")
        self.function_collection = client.get_or_create_collection("Function")

    async def process(self, _file):
        for name in self.json_names:
            _file.write("\n-----------------------------------------\n""正在处理dapp：" + name + "~\n")
            path = self.json_path + name
            if not os.path.exists(path):
                raise FileNotFoundError(f"路径不存在: {path}")

            # 读取数据集漏洞函数
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                dapp_name = data['name']
                _platform = data['platform']

                fault_list = list()
                for location in data['fault'].get('location', list()):
                    address, filename, src = location.split('#')
                    fault_begin, fault_offset = [int(offset) for offset in src.split(':')]
                    fault_message = {
                        "address": address,
                        "filename": filename,
                        "fault_begin_char": fault_begin,
                        "fault_offset_char": fault_offset
                    }
                    fault_list.append(fault_message)

                # 根据原始数据获取源代码列表
                tx_hash = list()
                fault_tx_hash_list = data['fault']['transaction_hash']
                faultless_tx_hash_list = data['faultless']['transaction_hash']
                for _f in fault_tx_hash_list:
                    tx_hash.extend(_f)
                tx_hash.extend(faultless_tx_hash_list)

                address_list: Set[str] = set()
                for _hash in tx_hash:
                    address = get_contract_address_from_tx(_hash, _platform)
                    if address is not None:
                        address_list.add(address)
                if not address_list:
                    _file.write("\n-----------------------------------------\n" + name + "合约地址为空！\n")
                    self.json_names.remove(name)
                    _file.write("\n" + str(self.json_names) + "\n")
                    continue
                _file.write("address list = " + str(address_list) + "\n")

                # 编译获取函数信息
                compile_result, dapp_codes = await self._load_compile_result(address_list, _platform)
                if not dapp_codes:
                    _file.write("\n-----------------------------------------\n" + name + "获取的合约代码为空！\n")
                    self.json_names.remove(name)
                    _file.write("\n" + str(self.json_names) + "\n")
                    continue
                # print("compile result = " + str(compile_result) + "\n")
                # print("dapp codes = " + str(dapp_codes) + "\n")

                for address in address_list:
                    if dapp_codes[address] is None or len(dapp_codes[address]) == 0:    # 获取的dapp源代码为空
                        _file.write(address + "获取的源代码为空！\n")
                        continue
                    codes = dapp_codes[address]['SourceCode']
                    if codes == '':
                        _file.write(address + "获取的源代码为空！\n")
                        continue
                    codes = codes[1: -1]
                    try:
                        codes = json.loads(codes)['sources']
                    except JSONDecodeError:
                        _file.write(address + "获取的源代码为空！\n")
                        continue
                    # 文档获取 + 清洗
                    code_dic = read_response_json(codes, data['name'])
                    formatted_code_dic = full_clean_solidity(code_dic)
                    total_ast = compile_result[address].ast
                    # 生成合约总结
                    block.extract_contract_summary_and_function_slice(formatted_code_dic, dapp_name, total_ast, _file, address, fault_list, self.contract_collection, self.function_collection)
            _file.write("\n-----------------------------------------\n" + name + "已经处理完成！\n")
            self.json_names.remove(name)
            _file.write("\n" + str(self.json_names) + "\n")

    def sol_to_json(self, direct_name: str):
        dapp_name, end = direct_name.split('.')
        for json_name in self.json_names:
            if json_name.startswith(dapp_name):
                return json_name

    async def _load_compile_result(self, contract_addresses: Set[str], network: str) -> (Dict[str, ContractCompileItem], Dict[str, json]):
        async def _create_task(_address: str, codes: json):
            return await ContractDao(downloader=ContractSourceDownloader(apikey="")).get_compile_item(_address, codes)

        code_list = dict()
        for contract_address in contract_addresses:
            if network == 'Ethereum':
                url = f'https://api.etherscan.io/api?module=contract&action=getsourcecode&address={contract_address}&apikey={settings.ETHERSCAN_API_KEY_1}'
            else:
                url = f'https://api.bscscan.com/api?module=contract&action=getsourcecode&address={contract_address}&apikey={settings.BNBCHAIN_API_KEY}'
            result = requests.get(url)
            time.sleep(0.5)
            result = result.json()
            if result['status'] != '1':  # 获取源代码失败
                code_list[contract_address] = {}
                continue
            code_list[contract_address] = result['result'][0]

        # load compile result of all contract
        tasks = [_create_task(addr, code_list[addr]) for addr in contract_addresses]
        result = await asyncio.gather(*tasks)
        return {addr: result[i] for i, addr in enumerate(contract_addresses)}, code_list

    async def direct_load_compile_result(self, code: str) -> ContractCompileItem:
        # load compile result of all contract
        return await ContractDao(downloader=ContractSourceDownloader(apikey="")).direct_get_compile_item(code)


if __name__ == '__main__':
    json_path = "source_code/json/"
    direct_path = "source_code/raw/"
    # direct_file_names = os.listdir(direct_path)
    # json_file_names = os.listdir(json_path)

    # file_names = os.listdir(json_path)

    # sushi_file_name = ['Nmbplatform.json']
    json_file_names = ['Alchemix.json', 'Beanstalk.json', 'Bearn.json', 'BTFinance.json', 'bZx.json', 'bZx0215.json', 'Cover.json','CreamFinance.json', 'DODO.json', 'ElevenFinance.json', 'FEGtoken.json', 'ForceDAO.json','FormationFi.json', 'FortressProtocol.json', 'Hegic.json', 'IndexedFinance.json', 'InverseFinance.json', 'JAY.json', 'LiFi.json', 'MerlinLab.json', 'MonoX.json', 'NBANFT.json', 'Nmbplatform.json', 'PancakeHunny.json', 'PopsicleFinance.json', 'PunkProtocol.json', 'QubitFinance.json', 'RevestFinance.json', 'RikkeiFinance.json', 'SaddleFinance.json', 'SashimiSwap.json', 'Soda.json', 'SpaceGodzilla.json', 'SushiSwap.json', 'UmbrellaNetwork.json', 'UraniumFinance.json', 'VisorFinance.json', 'WaultFinance.json', 'WildCredit.json', 'XCarnival.json']
    direct_file_names = ['Alchemix.sol', 'Beanstalk.sol', 'Cover Protocol.sol', 'CreamFinance-1.sol', 'Force DAO.sol', 'Formation.Fi.sol', 'Fortress Protocol.sol', 'Indexed Finance.sol', 'Li.Fi.sol', 'MERLIN LABS.sol', 'MonoX.sol', 'NBA NFT.sol', 'Nmbplatform.sol', 'Punk Protocol-1.sol', 'Punk Protocol-2.sol', 'Qubit Finance.sol', 'Revest Finance.sol', 'Rikkei Finance.sol', 'Saddle Finance.sol', 'SushiSwap.sol', 'Umbrella Network.sol', 'Uranium Finance-1.sol', 'Uranium Finance-2.sol', 'Uranium Finance-3.sol', 'Uranium Finance-4.sol', 'Uranium Finance-5.sol', 'Visor Finance.sol', 'XCarnival.sol']
    # yes_file_names = ['Alchemix.json', 'Beanstalk.json', 'Bearn.json', 'BTFinance.json', 'bZx.json', 'bZx0215.json', 'Cover.json','CreamFinance.json', 'DODO.json', 'ElevenFinance.json', 'FEGtoken.json', 'ForceDAO.json','FormationFi.json', 'FortressProtocol.json']
    handler = CodeHandler(direct_path, direct_file_names, json_path, json_file_names)
    for i in range(50):
        print("第" + str(i) + "次运行实验: ")
        file_path = "night_data/codes/" + str(i) + ".txt"
        try:
            # 主逻辑代码
            with open(file_path, "w", encoding="utf-8") as file:
                asyncio.run(handler.process(file))
                time.sleep(30)
        except Exception as e:
            try:
                time.sleep(30)
                # 异常处理代码（尝试写入异常信息到文件）
                with open(file_path, "a", encoding="utf-8") as file:  # 使用追加模式
                    file.write("\n\n--- 异常信息 ---\n")
                    traceback.print_exc(file=file)  # 写入完整堆栈跟踪

            except Exception as inner_e:
                # 如果连异常信息都写入失败，则打印到控制台
                print(f"无法写入异常信息到文件 {file_path}: {str(inner_e)}")

    # with open(file_path, "w", encoding="utf-8") as file:
    #     asyncio.run(CodeHandler(direct_path, direct_file_names, json_path, json_file_names).process(file))

    # with open(file_path, "w", encoding="utf-8") as file:
    #     asyncio.run(CodeHandler(direct_path, direct_file_names, json_path, json_file_names).dirct_process(file))

    # for i in range(1):
    #     print("第" + str(i) + "次运行实验: \n")
    #     file_path = "night_data/codes/" + str(i) + ".txt"
    #     try:
    #         # 主逻辑代码
    #         with open(file_path, "w", encoding="utf-8") as file:
    #             asyncio.run(CodeHandler(json_path, file_names).process(file))
    #     except Exception as e:
    #         try:
    #             # 异常处理代码（尝试写入异常信息到文件）
    #             with open(file_path, "a", encoding="utf-8") as file:  # 使用追加模式
    #                 file.write("\n\n--- 异常信息 ---\n")
    #                 traceback.print_exc(file=file)  # 写入完整堆栈跟踪
    #
    #         except Exception as inner_e:
    #             # 如果连异常信息都写入失败，则打印到控制台
    #             print(f"无法写入异常信息到文件 {file_path}: {str(inner_e)}")

    # list = ["Cover Protocol.sol", "CreamFinance-1.sol", "Force DAO.sol", "Formation.Fi.sol",
    #         "Fortress Protocol.sol", "Indexed Finance.sol", "Li.Fi.sol", "MERLIN LABS.sol",
    #         "MonoX.sol", "NBA NFT.sol", "Nmbplatform.sol", "Punk Protocol-1.sol", "Punk Protocol-2.sol",
    #         "Qubit Finance.sol", "Revest Finance.sol", "Rikkei Finance.sol", "Saddle Finance.sol",
    #         "Umbrella Network.sol", "Uranium Finance-1.sol", "Uranium Finance-2.sol", "Uranium Finance-3.sol",
    #         "Uranium Finance-4.sol", "Uranium Finance-5.sol", "Visor Finance.sol", "XCarnival.sol"]

    # for sol in list:
