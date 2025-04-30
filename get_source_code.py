import json
import os
import time

import requests
from web3 import Web3

# 配置Etherscan API
import settings
from downloaders.contract import TxToContractAddressDownloader, ContractSourceDownloader

ETHERSCAN_API_KEY = '4QP6SY9V7XXDJDEJBGC1NAI3KXRIU5CDEE'
ETHEREUM_NODE_URL = 'https://mainnet.chainnodes.org/5f63dc30-68dc-4e07-a446-5f68b03a66ed'

# 配置BscScan API
BNBCHAIN_API_KEY = 'M1Z8JTSB37EKZFD56BAGNHTRYYW4IRXIUT'
BNBCHAIN_NODE_URL = 'https://bsc-mainnet.chainnodes.org/5f63dc30-68dc-4e07-a446-5f68b03a66ed'


# 获取交易的合约地址
def get_contract_address_from_tx(tx_hash, network: str):
    if network == 'Ethereum':
        url = f'https://api.etherscan.io/api?module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey={settings.ETHERSCAN_API_KEY_1}'
    else:
        url = f'https://api.bscscan.com/api?module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey={settings.BNBCHAIN_API_KEY}'

    response = requests.get(url)
    time.sleep(1)
    data = response.json()
    if data['result'] is not None and isinstance(data['result'], dict) and data['result']['contractAddress'] is not None:
        return data['result']['contractAddress']
    else:
        if data['result'] is not None and isinstance(data['result'], dict) and data['result']['to'] is not None:
            return data['result']['to']
        return None


def get_contract_source_code(contract_address: str, api_key: str):
    url = f'https://api.etherscan.io/api?module=contract&action=getsourcecode&address={contract_address}&apikey={api_key}'
    result = requests.get(url)
    result = result.json()
    if result['status'] == '1' and result['result'][0]['SourceCode'] != '':  # 成功获取源代码
        result = result['result'][0]
        return json.loads(result['SourceCode'][1:-1])['sources']
    else:
        return {}


# 获取合约源码并保存到文件
def get_contract_source_code_and_save(contract_address, file_path, network):
    if network == 'E':
        url = f'https://api.etherscan.io/api?module=contract&action=getsourcecode&address={contract_address}&apikey={ETHERSCAN_API_KEY}'
    else:
        url = f'https://api.bscscan.com/api?module=contract&action=getsourcecode&address={contract_address}&apikey={BNBCHAIN_API_KEY}'
    response = requests.get(url)
    data = response.json()
    if data['status'] == '1':  # 成功获取源代码
        source_code = data['result'][0]['SourceCode']

        # 将源代码保存到指定路径
        if source_code:
            with open(file_path, 'w') as file:
                file.write(source_code)
            print(f'Source code saved to {file_path}')
        else:
            print(f'No source code available for contract: {contract_address}')
    else:
        print(f'Failed to retrieve source code for contract: {contract_address}')


# 主函数
def get_faulty_contract_source(address, output_dir, name, network, index):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)  # 创建输出目录
    print(f'Contract address: {address}')
    # 生成文件路径
    file_name = f'{name}-{index}.sol'  # 文件名为合约地址 + .sol 后缀
    file_path = os.path.join(output_dir, file_name)

    # 获取并保存合约源代码
    get_contract_source_code_and_save(address, file_path, network)


# Downloader 方式获取源码
async def get_source_by_txhash(tx_hash: str, apikey: str):
    # 获取合约地址
    address_downloader = TxToContractAddressDownloader(apikey=apikey)
    contract_address = await address_downloader.fetch_contract_address(tx_hash)

    # 获取源代码
    source_downloader = ContractSourceDownloader(apikey=apikey)
    source_code = await source_downloader.download(contract_address)
    return source_code


if __name__ == '__main__':
    # 输出文件夹路径
    output_directory = 'source_code'
    bug_name = '111test'

    trans = [
        "0xa9a1b8ea288eb9ad315088f17f7c7386b9989c95b4d13c81b69d5ddad7ffe61e"
    ]
    # 根据交易哈希获取合约地址
    contract_list = []
    for tran in trans:
        contract_address = get_contract_address_from_tx(tran)
        if contract_address is None:
            print(tran + "获取的合约地址为空")
            continue
        exits = False
        for contract in contract_list:
            if contract == contract_address:
                exits = True
        if exits is True:
            continue
        contract_list.append(contract_address)

    net = 'E'  # E Ethereum B BNBChain
    # 连接到以太坊节点
    if net == 'E':
        web3 = Web3(Web3.HTTPProvider(ETHEREUM_NODE_URL))
    else:
        web3 = Web3(Web3.HTTPProvider(BNBCHAIN_NODE_URL))
    # 获取这些交易涉及的合约源码
    i = 0
    for contract in contract_list:
        get_faulty_contract_source(contract, output_directory, bug_name, net, i)
        i = i + 1

    # # 根据交易哈希获取合约源代码
    # tx_hash = "0xcf68134279ba781a9de834af8f6ba2c4ceeaf32e78f2c445a274fa806c7f5c78"
    # apikey = "4QP6SY9V7XXDJDEJBGC1NAI3KXRIU5CDEE"
    # source_code = await get_source_by_txhash(tx_hash, apikey)
    # print(source_code)
