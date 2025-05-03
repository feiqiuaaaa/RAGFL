import chromadb

# cid = contracts.get('ids')
# fid = functions.get('ids')
# contract_collection.delete(ids=cid)
# function_collection.delete(ids=fid)

if __name__ == '__main__':
    # client = chromadb.HttpClient(host='47.102.102.136', port=8000)
    # contract_collection = client.get_or_create_collection("Contract")
    # function_collection = client.get_or_create_collection("Function")
    # contracts = contract_collection.get()
    # functions = function_collection.get()

    # new_contract_collection = client.get_or_create_collection("newContract")
    # new_function_collection = client.get_or_create_collection("newFunction")
    # new_contract = new_contract_collection.get()
    # new_function = new_function_collection.get()

    local_client = chromadb.PersistentClient(path="./chroma")
    local_contract_collection = local_client.get_or_create_collection("Contract")
    local_function_collection = local_client.get_or_create_collection("Function")
    local_contracts = local_contract_collection.get()
    local_functions = local_function_collection.get()

    contract_name = ["SushiSwap-SushiRoll.sol", "SushiSwap-UniswapV2Pair.sol", "SushiSwap-SushiMaker.sol"]
    contract = local_contract_collection.get(ids=contract_name)
    address = contract['metadatas'][0]['address']

    function_ = local_function_collection.get(where={"belong": {"$eq": "SushiSwap-SushiMaker.sol"}})
    print(function_)

    fault = local_function_collection.get(where={"is_fault": {"$eq": True}})
    print(fault['ids'])
    can_test_list = ['Alchemix', 'Cover Protocol',
                     'Formation.Fi', 'SushiSwap',
                     'Visor Finance', 'Umbrella Network',
                     'Fortress Protocol']

    online_ids = new_contract['ids']
    local_ids = local_contracts['ids']
    need_ids = []
    for online_id in online_ids:
        if online_id not in local_ids:
            need_ids.append(online_id)
    print(need_ids)

    special_list = ['CreamFinance', 'Punk Protocol', '']
    # ids = contracts['ids']
    # for cid in ids:
    #     c_list = cid.split('-')
    #     change = c_list[0]
    #     c_list.remove(c_list[0])
    #     changed = change.split('.')[0]
    #     changed_id = changed + '-' + '-'.join(c_list)
    #     c = contract_collection.get(ids=cid)
    #     c['ids'] = [changed_id]
    #     document = c['documents']
    #     metadata = c['metadatas']
    #
    #     exists = new_contract_collection.get(ids=changed_id)
    #     if len(exists.get('ids', [])) == 0:
    #         new_contract_collection.add(
    #             ids=[changed_id],
    #             documents=document,
    #             metadatas=metadata
    #         )
    # print("完成~")

    # ids = functions['ids']
    # for fid in ids:
    #     f_list = fid.split('-')
    #     change = f_list[0]
    #     f_list.remove(f_list[0])
    #     changed = change.split('.')[0]
    #     changed_id = changed + '-' + '-'.join(f_list)
    #     f = function_collection.get(ids=fid)
    #     f['ids'] = [changed_id]
    #     document = f['documents']
    #     metadata = f['metadatas']
    #
    #     exists = new_function_collection.get(ids=changed_id)
    #     if len(exists.get('ids', [])) == 0:
    #         new_function_collection.add(
    #             ids=[changed_id],
    #             documents=document,
    #             metadatas=metadata
    #         )

    # query_results = contract_collection.query(
    #     query_texts=["xxx"],
    #     n_results=40,
    #     include=["distances", "documents"]
    # )
    #
    # code_summary_list_str = ""
    # code_summary_list = query_results['documents']
    # _id_list = query_results['ids']
    # for _id, code_summary in zip(_id_list[0], code_summary_list[0]):
    #     code_summary_list_str = code_summary_list_str + "\n-----------------------------\n" + _id + ":\n" + code_summary
    #
    # print(code_summary_list_str)

    # id_list = ['MonoX.sol-IERC1155.sol', 'Punk Protocol-2.sol-ModelInterface.sol', 'SushiSwap.sol-SushiMaker.sol', 'Saddle Finance.sol-ISwap.sol', 'Li.Fi.sol-ICBridge.sol', 'SushiSwap.sol-UniswapV2ERC20.sol', 'Nmbplatform.sol-SafeERC20.sol', 'Beanstalk.sol-Decimal.sol', 'Alchemix.sol-IDetailedERC20.sol', 'Beanstalk.sol-LibIncentive.sol', 'Alchemix.sol-Math.sol', 'SushiSwap.sol-SushiRoll.sol', 'Cover Protocol.sol-Vesting.sol', 'Li.Fi.sol-SafeERC20.sol', 'MonoX.sol-Monoswap.sol', 'Qubit Finance.sol-BEP20Upgradeable.sol', 'Revest Finance.sol-IRevest.sol', 'Qubit Finance.sol-QBridgeToken.sol', 'Indexed Finance.sol-IUniswapV2Pair.sol', 'Uranium Finance-3.sol-Math.sol', 'Cover Protocol.sol-COVER.sol', 'CreamFinance-1.sol-CarefulMath.sol', 'SushiSwap.sol-IUniswapV2Factory.sol', 'SushiSwap.sol-UniswapV2Factory.sol', 'Li.Fi.sol-LibAsset.sol', 'SushiSwap.sol-IERC20.sol', 'Umbrella Network.sol-IStakingRewards.sol', 'Li.Fi.sol-WithdrawFacet.sol', 'MonoX.sol-IERC1155MetadataURI.sol', 'XCarnival.sol-IInterestRateModel.sol', 'MonoX.sol-IERC1155Receiver.sol', 'Beanstalk.sol-IDiamondLoupe.sol', 'SushiSwap.sol-Math.sol', 'Rikkei Finance.sol-InterestRateModel.sol', 'Cover Protocol.sol-ICOVER.sol', 'Formation.Fi.sol-ERC20.sol', 'SushiSwap.sol-BoringERC20.sol', 'Punk Protocol-2.sol-SafeMath.sol', 'Li.Fi.sol-AnyswapFacet.sol', 'Revest Finance.sol-IAddressRegistry.sol']
    #
    # cstr = ''
    # for _id in id_list:
    #     contract = contract_collection.get(ids=_id)
    #     cstr = cstr + "\n-----------------------------\n" + _id + ":\n" + contract['documents'][0]
    # print(cstr)
