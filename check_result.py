import chromadb

if __name__ == '__main__':
    result = [
        {"函数切片ID": "27301c7d-1a9c-11f0-971b-cc6b1e8c285a", "分数": 0.95},
        {"函数切片ID": "c47f95a3-1a94-11f0-b00a-cc6b1e8c285a", "分数": 0.93},
        {"函数切片ID": "3028c7a4-1a9e-11f0-a079-cc6b1e8c285a", "分数": 0.90},
        {"函数切片ID": "0d69a604-1a9b-11f0-b402-cc6b1e8c285a", "分数": 0.88},
        {"函数切片ID": "32fe7558-1a9c-11f0-a2e0-cc6b1e8c285a", "分数": 0.85},
        {"函数切片ID": "27301c7b-1a9c-11f0-a05d-cc6b1e8c285a", "分数": 0.82},
        {"函数切片ID": "27301c7c-1a9c-11f0-b220-cc6b1e8c285a", "分数": 0.80},
        {"函数切片ID": "c47f95a1-1a94-11f0-b4ce-cc6b1e8c285a", "分数": 0.78},
        {"函数切片ID": "3a73906b-1a9c-11f0-809b-cc6b1e8c285a", "分数": 0.75},
        {"函数切片ID": "32fe7556-1a9c-11f0-95db-cc6b1e8c285a", "分数": 0.70}
    ]
    slice_list = []
    for _ in result:
        slice_list.append(_.get("函数切片ID"))
    client = chromadb.HttpClient(host='47.102.102.136', port=8000)
    function_collection = client.get_or_create_collection("Function")
    result = function_collection.get(
        ids=slice_list
    )
    print(result)

    # ["27301c7d-1a9c-11f0-971b-cc6b1e8c285a", "27301c7b-1a9c-11f0-a05d-cc6b1e8c285a",
    #              "27301c7c-1a9c-11f0-b220-cc6b1e8c285a",
    #              "27301c79-1a9c-11f0-a684-cc6b1e8c285a", "27301c7a-1a9c-11f0-92ce-cc6b1e8c285a",
    #              "27301c7f-1a9c-11f0-9265-cc6b1e8c285a",
    #              "27301c7e-1a9c-11f0-8f9f-cc6b1e8c285a", "27301c78-1a9c-11f0-b6dc-cc6b1e8c285a",
    #              "27301c77-1a9c-11f0-9c81-cc6b1e8c285a",
    #              "27301c76-1a9c-11f0-8b2b-cc6b1e8c285a", "27301c75-1a9c-11f0-a42e-cc6b1e8c285a"]

    # ["27301c7d-1a9c-11f0-971b-cc6b1e8c285a", "27301c7b-1a9c-11f0-a05d-cc6b1e8c285a",
    #  "27301c7c-1a9c-11f0-b220-cc6b1e8c285a",
    #  "27301c79-1a9c-11f0-a684-cc6b1e8c285a", "27301c7a-1a9c-11f0-92ce-cc6b1e8c285a",
    #  "27301c7f-1a9c-11f0-9265-cc6b1e8c285a",
    #  "27301c7e-1a9c-11f0-8f9f-cc6b1e8c285a", "27301c78-1a9c-11f0-b6dc-cc6b1e8c285a",
    #  "27301c77-1a9c-11f0-9c81-cc6b1e8c285a",
    #  "27301c76-1a9c-11f0-8b2b-cc6b1e8c285a", "27301c75-1a9c-11f0-a42e-cc6b1e8c285a"]

    # ["27301c7d-1a9c-11f0-971b-cc6b1e8c285a", "27301c77-1a9c-11f0-9c81-cc6b1e8c285a",
    #              "a2c8f953-1a8f-11f0-9dfd-cc6b1e8c285a",
    #              "a2c8f955-1a8f-11f0-8d53-cc6b1e8c285a", "a2c8f954-1a8f-11f0-a68f-cc6b1e8c285a",
    #              "27301c7b-1a9c-11f0-a05d-cc6b1e8c285a",
    #              "27301c7c-1a9c-11f0-b220-cc6b1e8c285a", "a2c8f952-1a8f-11f0-ac2d-cc6b1e8c285a",
    #              "32fe7558-1a9c-11f0-a2e0-cc6b1e8c285a",
    #              "27301c7a-1a9c-11f0-92ce-cc6b1e8c285a"]
