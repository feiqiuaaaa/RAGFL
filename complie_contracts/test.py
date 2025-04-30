import asyncio
import json
from typing import List, Dict, Set

import requests
from complie_contracts.ContractDao import ContractDao, ContractCompileItem
from complie_contracts.extract_slice_by_ast import parse_ast, src_to_line_numbers
from downloaders.contract import ContractSourceDownloader

SCAN_APIKEYS = {
    'Ethereum': [
        'https://api.etherscan.io/api?apikey=4QP6SY9V7XXDJDEJBGC1NAI3KXRIU5CDEE',
        'https://api.etherscan.io/api?apikey=J9996KUX8WNA5I86WY67ZMZK72SST1BIW8',
    ],
    'BNBChain': [
        'https://api.bscscan.com/api?apikey=3FYU1X8HNHNQ287PUIXZBFYWT78TBPG4P6',
    ],
}

apikeys = SCAN_APIKEYS.get('Ethereum')


def get_contract_source_code(contract_address: str, eth_api_key: str):
    url = f'https://api.etherscan.io/api?module=contract&action=getsourcecode&address={contract_address}&apikey={eth_api_key}'
    result = requests.get(url)
    result = result.json()
    result = result['result'][0]
    return json.loads(result['SourceCode'][1:-1])['sources']


async def _load_compile_result(contract_addresses: Set[str], api_key: str) -> Dict[str, ContractCompileItem]:
    async def _create_task(_address: str):
        return await ContractDao(downloader=ContractSourceDownloader(
            apikey="https://api.etherscan.io/api?apikey=4QP6SY9V7XXDJDEJBGC1NAI3KXRIU5CDEE",
        )).get_compile_item(_address, api_key)

    # load compile result of all contract
    tasks = [_create_task(addr) for addr in contract_addresses]
    result = await asyncio.gather(*tasks)
    return {addr: result[i] for i, addr in enumerate(contract_addresses)}


async def direct_load_compile_result(content: json) -> Dict[str, ContractCompileItem]:
    async def _create_task(content: json):
        return await ContractDao(downloader=ContractSourceDownloader(
            apikey="",
        )).direct_get_compile_item(content)

    # load compile result of all contract
    tasks = _create_task(content)
    result = await asyncio.gather(*tasks)
    return {addr: result[i] for i, addr in enumerate(contract_addresses)}


async def main():
    add_list = {"0xe11fc0b43ab98eb91e9836129d1ee7c3bc95df50"}
    api = "4QP6SY9V7XXDJDEJBGC1NAI3KXRIU5CDEE"
    result = await _load_compile_result(add_list, api)

    total_ast = result.get("0xe11fc0b43ab98eb91e9836129d1ee7c3bc95df50").ast
    codes = get_contract_source_code("0xe11fc0b43ab98eb91e9836129d1ee7c3bc95df50", api)
    metadata_list = {}
    for key in codes.keys():
        ast = total_ast[key]
        metadata = parse_ast(ast)
        print(key + " : " + str(codes[key]) + "\n")
        for each in metadata:
            start_line, end_line = src_to_line_numbers(each['src'], codes[key]['content'])
            each['src'] = str(start_line) + "#" + str(end_line)
        metadata_list[key] = metadata
    print(metadata_list)


if __name__ == '__main__':
    asyncio.run(main())  # 正确启动异步入口
