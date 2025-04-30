import os
import re

RAW_JSON_PATH = 'source_code/raw/'

PROJECT_PATH, _ = os.path.split(os.path.realpath(__file__))
PC_TRACER_RELATED_PATH = 'misc/tracer.js'
with open(os.path.join(PROJECT_PATH, PC_TRACER_RELATED_PATH), 'r') as f:
    PC_TRACER = f.read()
    PC_TRACER = PC_TRACER[9:]
    PC_TRACER = re.sub('\n|\t', '', PC_TRACER)

TYPED_AST_CODE_RELATED_PATH = 'misc/ast.js'
with open(os.path.join(PROJECT_PATH, TYPED_AST_CODE_RELATED_PATH), 'r') as f:
    TYPED_AST_CODE = f.read()

SOLCJS_CODE_RELATED_PATH = 'misc/solcjs.js'
with open(os.path.join(PROJECT_PATH, SOLCJS_CODE_RELATED_PATH), 'r') as f:
    SOLCJS_CODE = f.read()

CACHE_DIR = os.path.join(PROJECT_PATH, 'data/cache')

TMP_FILE_DIR = os.path.join(PROJECT_PATH, 'tmp')
if not os.path.exists(TMP_FILE_DIR):
    os.makedirs(TMP_FILE_DIR)

NODE_PATH = 'node'

SCAN_APIKEYS = {
    'Ethereum': [
        'https://api.etherscan.io/api?apikey=7MM6JYY49WZBXSYFDPYQ3V7V3EMZWE4KJK',
        'https://api.etherscan.io/api?apikey=J9996KUX8WNA5I86WY67ZMZK72SST1BIW8',
    ],
    'BNBChain': [
        'https://api.bscscan.com/api?apikey=3FYU1X8HNHNQ287PUIXZBFYWT78TBPG4P6',
    ],
}
JSONRPCS = {
    'Ethereum': [
        'https://mainnet.chainnodes.org/965e82de-fa68-404c-82b9-6f078bdb3c30',
    ],
    'BNBChain': [
        'https://bsc-mainnet.chainnodes.org/965e82de-fa68-404c-82b9-6f078bdb3c30',
    ]
}

ETHERSCAN_API_KEY_1 = '4QP6SY9V7XXDJDEJBGC1NAI3KXRIU5CDEE'
ETHERSCAN_API_KEY_2 = 'Y3HRQPY2RXG6CQNJSV7QJXDZ1S2SCKTVTD'
ETHEREUM_NODE_URL = 'https://mainnet.chainnodes.org/5f63dc30-68dc-4e07-a446-5f68b03a66ed'

# 配置BscScan API
BNBCHAIN_API_KEY = 'M1Z8JTSB37EKZFD56BAGNHTRYYW4IRXIUT'
BNBCHAIN_NODE_URL = 'https://bsc-mainnet.chainnodes.org/5f63dc30-68dc-4e07-a446-5f68b03a66ed'
