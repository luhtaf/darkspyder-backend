def ResponseError(msg, status):
    return {
        "err":True,
        "msg":msg,
        "status":status
    }

def ResponseSuccess(data, status):
    return {
        "status" : status,
        "values" : {
            "rows" : data,
            "total" : len(data)
        }
    }

def ResponseSuccessPagination(page, size, total_count, result, status):
    return {
        "page": page,
        "size": size,
        "total": total_count, 
        "current_page_data": result['hits']['hits'],
        "status": status
    }