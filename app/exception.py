# exception.py

class AlreadyExistsError(Exception):
    """
    Raised when attempting to create an item that already exists.
    """
    pass


class NotFoundError(Exception):
    """
    Raised when an expected item is not found.
    """
    pass


class InvalidInputError(Exception):
    """
    Raised when user input or function parameters are invalid.
    """
    pass


class CategoryInUseError(Exception):
    """
    Raised when attempting to delete a category that is still in use.
    """
    pass
