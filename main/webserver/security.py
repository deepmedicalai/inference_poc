



def validate_edge_token(request):

    if request is None:
        return False, None

    token = request.headers.get("X-Api-Key")

    if (token is not None) and (token == "edge0001-key"):
        return True, token
    else:
        return False, None