from src.producers.text_editor import trunc_str


def test_trunc_str_with_long_text():
    text = "This is a very long text that needs to be truncated"
    max_length = 20
    result = trunc_str(text, max_length)
    assert len(result) == max_length + 3
    assert result == "This is a very long ..."


def test_trunc_str_with_short_text():
    text = "Short text"
    max_length = 20
    result = trunc_str(text, max_length)
    assert result == text
    assert len(result) == len(text)


def test_trunc_str_with_exact_length():
    text = "Exact twenty chars!!"
    max_length = 20
    result = trunc_str(text, max_length)
    assert result == text
    assert len(result) == max_length
