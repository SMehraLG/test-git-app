from smoke_python import add, subtract


def test_add():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-2, -3) == -5


def test_subtract():
    assert subtract(5, 2) == 3
