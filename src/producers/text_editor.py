def trunc_str(text, max_length):
    return text[:max_length] + '...' if len(text) > max_length else text
