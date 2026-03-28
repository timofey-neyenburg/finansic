def string_calc(expression: str) -> float:
    allowed_symbols = "0123456789.+-*() "
    for symbol in expression:
        if symbol not in allowed_symbols:
            raise ValueError(f"Invalid symbol: {symbol}")
    return eval(expression)

def calc_input(prompt: str, allow_none: bool = False) -> float | None:
    input_value = input(prompt)
    if allow_none and input_value == "":
        return None
    return string_calc(input_value)