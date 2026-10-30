from testify import TestCase, assert_equal
from calculator import add


class CalculatorTest(TestCase):
    def test_add(self):
        assert_equal(add(2, 3), 5)
