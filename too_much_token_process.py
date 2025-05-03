import chromadb

import llm

if __name__ == '__main__':
    client = chromadb.PersistentClient(path="./chroma")
    contract_collection = client.get_or_create_collection("Contract")
    function_collection = client.get_or_create_collection("Function")

    bug_summary = '一、关键异常点\n1.异常代币铸造与销毁：故障交易0x90fb0c9976...中向0xe11fc0b43ab98eb91e9836129d1ee7c3bc95df50铸造53,612 DIGG后立即销毁604,340,502 DIGG，并通过Uniswap/Sushiswap池完成WBTC→ETH→SUSHI异常大额兑换（输出3,712,589,956,677,208 SUSHI）。\n2.流动性池价格操控：攻击者利用DIGG合约未授权铸造漏洞，向WBTC/ETH池注入虚假流动性，通过跨池兑换将虚增DIGG价值转化为ETH，最终兑换成超额SUSHI。\n3.代币循环路径异常：通过路由合约0xe11fc0b43ab98eb91e9836129d1ee7c3bc95df50实现DIGG→WBTC→ETH→SUSHI跨池兑换，形成异常资金闭环。\n\n二、漏洞原因分析\n根本原因为DIGG合约未授权铸造与流动性池检测缺失。具体漏洞点包括：1.代币合约0x798d1be841a82a273720ce31c822c61a67a601c3的mint函数无权限控制；2.Uniswap V2使用恒定乘积算法未验证真实流通量；3.跨池兑换路由未校验代币供应量真实性，允许虚假流动性操纵价格。\n\n三、攻击路径还原\n1.调用DIGG合约铸造604,340,502代币并转入自身地址；2.向Uniswap V2的WBTC/ETH池注入虚假DIGG和WBTC流动性；3.通过路由合约执行DIGG→WBTC→ETH三明治交易；4.在Sushiswap池利用ETH兑换获取3.7万亿SUSHI；5.销毁剩余DIGG掩盖攻击痕迹。关键函数：0x89afcb44（添加流动性）和0x022c0d9f（闪电兑换）。\n\n四、trace调用链（故障交易）\n0x51841d9afe10fe55571bdb8f4af1060415003528→0xe11fc0b43ab98eb91e9836129d1ee7c3bc95df50→0x9a13867048e01c663ce8ce2fe0cdae69ff9f35e3→0x2260fac5e5542a773aa44fbcfedf7c193bc2c599→0xceff51756c56ceffca006cd410b03ffc46dd3a58→0x795065dcc9f64b5614c407a6efdc400da6221fb0→0x8798249c2e607446efb7ad49ec89dd1865ff4272'
    final_contracts = ['SushiSwap-SushiToken.sol', 'SushiSwap-MasterChef.sol', 'SushiSwap-SushiBar.sol', 'SushiSwap-SushiMaker.sol', 'SushiSwap-UniswapV2Pair.sol', 'SushiSwap-IUniswapV2Pair.sol', 'SushiSwap-UniswapV2Router02.sol', 'SushiSwap-IUniswapV2Router02.sol', 'SushiSwap-SushiRoll.sol', 'SushiSwap-Migrator.sol', 'SushiSwap-ERC20.sol', 'SushiSwap-ERC20Mock.sol', 'SushiSwap-IERC20.sol', 'SushiSwap-SafeERC20.sol', 'SushiSwap-TransferHelper.sol', 'SushiSwap-SafeMath.sol']
    function_str = ""
    for contract_name in final_contracts:
        function_list = function_collection.get(
            where={"belong": {"$eq": contract_name}}
        )
        contract = contract_collection.get(ids=contract_name)
        if len(contract.get('documents')) == 0:
            address = ''
        else:
            address = contract['metadatas'][0]['address']
        if len(function_list.get('documents')) == 0:
            continue
        ids = function_list.get('ids')
        metadatas = function_list.get('metadatas')
        documents = function_list.get('documents')
        for fid, metadata, document in zip(ids, metadatas, documents):
            metadata['is_fault'] = ''
            function_str += "\n------------------------------------------------\n函数切片ID: " + fid + "\n所属合约地址" + address + "\n元数据:" + str(
                metadata) + "\n函数切片:\n" + document

    location_variables = {
        'bug_summary': bug_summary,
        'function_str': function_str,
    }
    system_prompt = llm.load_prompt("prompt/location_trace_chain_system_prompt")
    user_prompt = llm.load_prompt("prompt/location_trace_chain_user_prompt", location_variables)
    location_result = llm.get_summary_from_llm(system_prompt, user_prompt)
    if location_result[0] != 'stop':
        print(' error! message:' + location_result[0])
    location_result = location_result[1]
    # print("------------------------------------------------" + "\n" + rerank_result)
    print("\n------------------------------------------------" + "\n故障定位结果：\n" + location_result)
