"""Sample Python file for testing tree-sitter parsing."""


class MyClass:
    """A sample class."""
    
    def __init__(self, name):
        """Initialize the class."""
        self.name = name
    
    def process(self, data):
        """Process some data."""
        return data.upper()
    
    async def async_method(self):
        """An async method."""
        await some_operation()


def my_function(x, y):
    """A sample function."""
    return x + y


async def async_function():
    """An async function."""
    await something()


@decorator
def decorated_function():
    """A decorated function."""
    pass


@dataclass
class DataClass:
    """A dataclass."""
    name: str
    value: int