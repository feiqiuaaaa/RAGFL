import json
import os
import urllib.parse
from typing import Dict

from downloaders.defs import JSONRPCDownloader, EtherscanDownloader
from settings import CACHE_DIR


class ContractBytecodeDownloader(JSONRPCDownloader):
    def get_request_param(self, contract_address: str, quantity: str = 'latest') -> Dict:
        data = {
            "id": 1,
            "jsonrpc": "2.0",
            "params": [
                contract_address.lower(),
                quantity,
            ],
            "method": "eth_getCode"
        }
        return {
            "url": self.rpc_url,
            "json": data,
        }

    async def _preprocess(self, contract_address: str, **kwargs):
        path = os.path.join(CACHE_DIR, 'bytecode', '%s.json' % contract_address)
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            return json.load(f)

    async def _process(self, result: str, **kwargs):
        result = json.loads(result)
        result = result['result']

        # cache data
        contract_address = kwargs['contract_address']
        path = os.path.join(CACHE_DIR, 'bytecode')
        if not os.path.exists(path):
            os.makedirs(path)
        path = os.path.join(path, '%s.json' % contract_address)
        with open(path, 'w') as f:
            json.dump(result, f)
        return result


class ContractSourceDownloader(EtherscanDownloader):
    def get_request_param(self, contract_address: str) -> Dict:
        query_params = urllib.parse.urlencode({
            "module": "contract",
            "action": "getsourcecode",
            "address": contract_address.lower(),
        })
        return {"url": '{}&{}'.format(self.apikey, query_params)}

    async def _preprocess(self, contract_address: str, **kwargs):
        path = os.path.join(CACHE_DIR, 'source', '%s.json' % contract_address)
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            return json.load(f)

    async def _process(self, result: str, **kwargs):
        result = json.loads(result)
        result = result['result'][0]

        # cache data
        contract_address = kwargs['contract_address']
        path = os.path.join(CACHE_DIR, 'source')
        if not os.path.exists(path):
            os.makedirs(path)
        path = os.path.join(path, '%s.json' % contract_address)
        with open(path, 'w') as f:
            json.dump(result, f)
        return result


class TxToContractAddressDownloader(EtherscanDownloader):
    def get_request_param(self, tx_hash: str) -> Dict:
        query_params = urllib.parse.urlencode({
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash,
            "apikey": self.apikey  # 正确传递API密钥
        })
        return {"url": f"{self.base_url}?{query_params}"}

    async def fetch_contract_address(self, tx_hash: str) -> str:
        params = self.get_request_param(tx_hash)
        response = await self._fetch(params)
        result = json.loads(response)
        contract_address = result.get('result', {}).get('contractAddress')
        if not contract_address:
            raise ValueError("交易不是合约创建类型或地址未找到")
        return contract_address
