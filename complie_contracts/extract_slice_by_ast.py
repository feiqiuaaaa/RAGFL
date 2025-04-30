import json
from collections import defaultdict
import bisect


def parse_ast(ast) -> {}:
    contracts = {}
    events = {}
    state_vars = defaultdict(list)
    modifiers = {}

    # 遍历所有节点识别合约定义
    for node in ast['nodes']:
        if node['nodeType'] == 'ContractDefinition':
            contract_id = node['id']
            contracts[contract_id] = {
                'name': node['name'],
                'baseContracts': [base['baseName']['referencedDeclaration'] for base in node.get('baseContracts', [])],
                'nodes': []
            }

            # 处理合约内元素
            for sub_node in node['nodes']:
                contracts[contract_id]['nodes'].append(sub_node)
                # 收集状态变量
                if sub_node['nodeType'] == 'VariableDeclaration' and sub_node.get('stateVariable'):
                    state_vars[contract_id].append({
                        'id': sub_node['id'],
                        'name': sub_node['name'],
                        'type': sub_node['typeName']['typeDescriptions']['typeString']
                    })
                # 收集事件
                elif sub_node['nodeType'] == 'EventDefinition':
                    events[sub_node['id']] = sub_node['name']
                # 收集修饰器
                elif sub_node['nodeType'] == 'ModifierDefinition':
                    modifiers[sub_node['id']] = sub_node['name']

    # 分析函数定义
    def analyze_function(func_node, contract_name):
        metadata = {
            'name': func_node.get('name') or 'constructor',
            'visibility': func_node.get('visibility', ''),
            'stateMutability': func_node.get('stateMutability', ''),
            'parameters': [],
            'returns': [],
            'permission_check': False,
            'reentrancy_guard': False,
            'events': [],
            'errors': [],
            'contract': contract_name,
            'external_calls': [],
            'state_vars': {'read': [], 'written': []},
            'src': func_node['src']
        }

        # 处理参数和返回值
        for param in func_node.get('parameters', {}).get('parameters', []):
            metadata['parameters'].append({
                'name': param['name'],
                'type': param['typeName']['typeDescriptions']['typeString']
            })

        for ret in func_node.get('returnParameters', {}).get('parameters', []):
            metadata['returns'].append({
                'name': ret.get('name', ''),
                'type': ret['typeName']['typeDescriptions']['typeString']
            })

        # 检查权限修饰器
        for mod in func_node.get('modifiers', []):
            if modifiers.get(mod['modifierName']['referencedDeclaration']) == 'onlyOwner':
                metadata['permission_check'] = True

        # 分析函数体
        if 'body' in func_node:
            analyze_body(func_node['body'], metadata, events)

        return metadata

    # 递归分析函数体
    def analyze_body(node, metadata, events):
        if isinstance(node, dict):
            # 检测事件触发
            if node.get('nodeType') == 'EmitStatement':
                event_id = node['eventCall']['expression']['referencedDeclaration']
                metadata['events'].append(events.get(event_id, 'Unknown'))

            # 检测错误信息
            if node.get('nodeType') == 'FunctionCall' and node['expression'].get('name') == 'require':
                if len(node['arguments']) > 1 and node['arguments'][1]['nodeType'] == 'Literal':
                    metadata['errors'].append(node['arguments'][1]['value'])

            # 检测状态变量访问
            if node.get('nodeType') == 'Identifier' and node.get('referencedDeclaration'):
                for var in state_vars.values():
                    for v in var:
                        if v['id'] == node['referencedDeclaration']:
                            if is_write_operation(node):
                                metadata['state_vars']['written'].append(v['name'])
                            else:
                                metadata['state_vars']['read'].append(v['name'])

            # 递归处理子节点
            for key in node:
                if isinstance(node[key], (dict, list)):
                    analyze_body(node[key], metadata, events)

        elif isinstance(node, list):
            for item in node:
                analyze_body(item, metadata, events)

    def is_write_operation(node):
        # 简化判断：如果父节点是Assignment的左值则为写操作
        parent = node.get('parent', {})
        if parent.get('nodeType') == 'Assignment' and parent['leftHandSide'] == node:
            return True
        return False

    # 主处理逻辑
    results = []
    for contract in contracts.values():
        for node in contract['nodes']:
            if node['nodeType'] == 'FunctionDefinition':
                func_meta = analyze_function(node, contract['name'])
                results.append(func_meta)

            elif node['nodeType'] == 'ModifierDefinition':
                results.append({
                    'name': node['name'],
                    'type': 'modifier',
                    'contract': contract['name'],
                    'src': node['src']
                })

    return results


def src_to_line_numbers(start, length, content: str):
    # 生成行偏移量列表（每行的起始字符位置）
    line_offsets = [0]
    for i, c in enumerate(content):
        if c == '\n':
            line_offsets.append(i + 1)

    # 计算字符位置范围
    start_pos = start
    end_pos = start_pos + length - 1  # 包含结束位置

    # 处理超出文件末尾的情况
    max_pos = len(content) - 1
    if end_pos > max_pos:
        end_pos = max_pos

    # 查找对应的行号
    start_line_idx = bisect.bisect_right(line_offsets, start_pos) - 1
    end_line_idx = bisect.bisect_right(line_offsets, end_pos) - 1

    # 转换为从1开始的行号
    return start_line_idx + 1, end_line_idx + 1


# 使用示例
if __name__ == '__main__':
    # with open('ast.json') as f:
    #     ast_data = json.load(f)

    content = '// SPDX-License-Identifier: MIT\n// P1 - P3: OK\npragma solidity 0.6.12;\nimport "./libraries/BoringMath.sol";\nimport "./libraries/BoringERC20.sol";\n\nimport "./uniswapv2/interfaces/IUniswapV2ERC20.sol";\nimport "./uniswapv2/interfaces/IUniswapV2Pair.sol";\nimport "./uniswapv2/interfaces/IUniswapV2Factory.sol";\n\nimport "./BoringOwnable.sol";\n\n// SushiMaker is MasterChef\'s left hand and kinda a wizard. He can cook up Sushi from pretty much anything!\n// This contract handles "serving up" rewards for xSushi holders by trading tokens collected from fees for Sushi.\n\n// T1 - T4: OK\ncontract SushiMaker is BoringOwnable {\n    using BoringMath for uint256;\n    using BoringERC20 for IERC20;\n\n    // V1 - V5: OK\n    IUniswapV2Factory public immutable factory;\n    //0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac\n    // V1 - V5: OK\n    address public immutable bar; \n    //0x8798249c2E607446EfB7Ad49eC89dD1865Ff4272\n    // V1 - V5: OK\n    address private immutable sushi;\n    //0x6B3595068778DD592e39A122f4f5a5cF09C90fE2\n    // V1 - V5: OK\n    address private immutable weth; \n    //0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2\n\n    // V1 - V5: OK\n    mapping(address => address) internal _bridges;\n\n    // E1: OK\n    event LogBridgeSet(address indexed token, address indexed bridge);\n    // E1: OK\n    event LogConvert(address indexed server, address indexed token0, address indexed token1, uint256 amount0, uint256 amount1, uint256 amountSUSHI);\n\n\n    constructor (address _factory, address _bar, address _sushi, address _weth) public {\n       factory = IUniswapV2Factory(_factory);\n       bar = _bar;\n       sushi = _sushi;\n       weth = _weth;\n    }\n    \n    // F1 - F10: OK\n    // C1 - C24: OK\n    function bridgeFor(address token) public view returns (address bridge) {\n        bridge = _bridges[token];\n        if (bridge == address(0)) {\n            bridge = weth;\n        }\n    }\n\n    // F1 - F10: OK\n    // C1 - C24: OK\n    function setBridge(address token, address bridge) external onlyOwner {\n        // Checks\n        require(token != sushi && token != weth && token != bridge, "SushiMaker: Invalid bridge");\n\n        // Effects\n        _bridges[token] = bridge;\n        emit LogBridgeSet(token, bridge);\n    }\n\n    // M1 - M5: OK\n    // C1 - C24: OK\n    // C6: It\'s not a fool proof solution, but it prevents flash loans, so here it\'s ok to use tx.origin\n    modifier onlyEOA() {\n        // Try to make flash-loan exploit harder to do.\n        require(msg.sender == tx.origin, "SushiMaker: must use EOA");\n        _;\n    }\n\n    // F1 - F10: OK\n    // F3: _convert is separate to save gas by only checking the \'onlyEOA\' modifier once in case of convertMultiple\n    // F6: There is an exploit to add lots of SUSHI to the bar, run convert, then remove the SUSHI again.\n    //     As the size of the SushiBar has grown, this requires large amounts of funds and isn\'t super profitable anymore\n    //     The onlyEOA modifier prevents this being done with a flash loan.\n    // C1 - C24: OK\n    function convert(address token0, address token1) external onlyEOA() {\n        _convert(token0, token1);\n    }\n\n    // F1 - F10: OK, see convert\n    // C1 - C24: OK\n    // C3: Loop is under control of the caller\n    function convertMultiple(address[] calldata token0, address[] calldata token1) external onlyEOA() {\n        // TODO: This can be optimized a fair bit, but this is safer and simpler for now\n        uint256 len = token0.length;\n        for(uint256 i=0; i < len; i++) {\n            _convert(token0[i], token1[i]);\n        }\n    }\n\n    // F1 - F10: OK\n    // C1- C24: OK\n    function _convert(address token0, address token1) internal {\n        // Interactions\n        // S1 - S4: OK\n        IUniswapV2Pair pair = IUniswapV2Pair(factory.getPair(token0, token1));\n        require(address(pair) != address(0), "SushiMaker: Invalid pair");\n        // balanceOf: S1 - S4: OK\n        // transfer: X1 - X5: OK\n        IERC20(address(pair)).safeTransfer(address(pair), pair.balanceOf(address(this)));\n        // X1 - X5: OK\n        (uint256 amount0, uint256 amount1) = pair.burn(address(this));\n        if (token0 != pair.token0()) {\n            (amount0, amount1) = (amount1, amount0);\n        }\n        emit LogConvert(msg.sender, token0, token1, amount0, amount1, _convertStep(token0, token1, amount0, amount1));\n    }\n\n    // F1 - F10: OK\n    // C1 - C24: OK\n    // All safeTransfer, _swap, _toSUSHI, _convertStep: X1 - X5: OK\n    function _convertStep(address token0, address token1, uint256 amount0, uint256 amount1) internal returns(uint256 sushiOut) {\n        // Interactions\n        if (token0 == token1) {\n            uint256 amount = amount0.add(amount1);\n            if (token0 == sushi) {\n                IERC20(sushi).safeTransfer(bar, amount);\n                sushiOut = amount;\n            } else if (token0 == weth) {\n                sushiOut = _toSUSHI(weth, amount);\n            } else {\n                address bridge = bridgeFor(token0);\n                amount = _swap(token0, bridge, amount, address(this));\n                sushiOut = _convertStep(bridge, bridge, amount, 0);\n            }\n        } else if (token0 == sushi) { // eg. SUSHI - ETH\n            IERC20(sushi).safeTransfer(bar, amount0);\n            sushiOut = _toSUSHI(token1, amount1).add(amount0);\n        } else if (token1 == sushi) { // eg. USDT - SUSHI\n            IERC20(sushi).safeTransfer(bar, amount1);\n            sushiOut = _toSUSHI(token0, amount0).add(amount1);\n        } else if (token0 == weth) { // eg. ETH - USDC\n            sushiOut = _toSUSHI(weth, _swap(token1, weth, amount1, address(this)).add(amount0));\n        } else if (token1 == weth) { // eg. USDT - ETH\n            sushiOut = _toSUSHI(weth, _swap(token0, weth, amount0, address(this)).add(amount1));\n        } else { // eg. MIC - USDT\n            address bridge0 = bridgeFor(token0);\n            address bridge1 = bridgeFor(token1);\n            if (bridge0 == token1) { // eg. MIC - USDT - and bridgeFor(MIC) = USDT\n                sushiOut = _convertStep(bridge0, token1,\n                    _swap(token0, bridge0, amount0, address(this)),\n                    amount1\n                );\n            } else if (bridge1 == token0) { // eg. WBTC - DSD - and bridgeFor(DSD) = WBTC\n                sushiOut = _convertStep(token0, bridge1,\n                    amount0,\n                    _swap(token1, bridge1, amount1, address(this))\n                );\n            } else {\n                sushiOut = _convertStep(bridge0, bridge1, // eg. USDT - DSD - and bridgeFor(DSD) = WBTC\n                    _swap(token0, bridge0, amount0, address(this)),\n                    _swap(token1, bridge1, amount1, address(this))\n                );\n            }\n        }\n    }\n\n    // F1 - F10: OK\n    // C1 - C24: OK\n    // All safeTransfer, swap: X1 - X5: OK\n    function _swap(address fromToken, address toToken, uint256 amountIn, address to) internal returns (uint256 amountOut) {\n        // Checks\n        // X1 - X5: OK\n        IUniswapV2Pair pair = IUniswapV2Pair(factory.getPair(fromToken, toToken));\n        require(address(pair) != address(0), "SushiMaker: Cannot convert");\n\n        // Interactions\n        // X1 - X5: OK\n        (uint256 reserve0, uint256 reserve1,) = pair.getReserves();\n        uint256 amountInWithFee = amountIn.mul(997);\n        if (fromToken == pair.token0()) {\n            amountOut = amountIn.mul(997).mul(reserve1) / reserve0.mul(1000).add(amountInWithFee);\n            IERC20(fromToken).safeTransfer(address(pair), amountIn);\n            pair.swap(0, amountOut, to, new bytes(0));\n            // TODO: Add maximum slippage?\n        } else {\n            amountOut = amountIn.mul(997).mul(reserve0) / reserve1.mul(1000).add(amountInWithFee);\n            IERC20(fromToken).safeTransfer(address(pair), amountIn);\n            pair.swap(amountOut, 0, to, new bytes(0));\n            // TODO: Add maximum slippage?\n        }\n    }\n\n    // F1 - F10: OK\n    // C1 - C24: OK\n    function _toSUSHI(address token, uint256 amountIn) internal returns(uint256 amountOut) {\n        // X1 - X5: OK\n        amountOut = _swap(token, sushi, amountIn, bar);\n    }\n}\n'
    start, end = src_to_line_numbers("3574:738:0", content)
    print(str(start) + "--" + str(end))

    # metadata = parse_ast(ast_data)
