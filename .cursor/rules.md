# Cursor Rules for RAGPilot Project
# Clean Code + Python flake8 Standards

## Core Principles

### Clean Code Philosophy
- Code should be self-explanatory without excessive comments
- Function and variable names should clearly express their purpose
- Prefer composition over inheritance
- Follow single responsibility principle
- Keep functions small and focused
- Avoid deep nesting (max 3 levels)

### Python Standards (flake8 compliant)
- Line length: max 88 characters (Black standard)
- Use 4 spaces for indentation (no tabs)
- Two blank lines between top-level functions/classes
- One blank line between methods in a class
- Import organization: standard library, third-party, local imports

## Naming Conventions

### Variables and Functions
- Use snake_case for variables and functions
- Use descriptive names: `user_count` not `uc`
- Boolean variables: prefix with `is_`, `has_`, `can_`, `should_`
- Private methods: prefix with single underscore `_method_name`

### Classes and Constants
- Use PascalCase for classes: `UserManager`, `DataProcessor`
- Use UPPER_SNAKE_CASE for constants: `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT`

### Files and Modules
- Use snake_case for file names: `user_manager.py`, `data_processor.py`
- Package names should be short and lowercase

## Function Design

### Function Rules
- Max 20 lines per function (prefer 5-10 lines)
- Max 4 parameters (use dataclasses/kwargs for more)
- Single return point when possible
- No nested functions beyond 2 levels
- Pure functions when possible (no side effects)

### Error Handling
- Use specific exception types, not bare `except:`
- Handle exceptions at the appropriate level
- Fail fast - validate inputs early
- Use context managers for resource management

## Code Organization

### Import Order
```python
# Standard library
import os
import sys

# Third-party packages
import pandas as pd
import requests

# Local imports
from utils.database import get_connection
from models.user import User
```

### File Structure
- Keep related functionality together
- Separate concerns into different modules
- Use `__init__.py` for package initialization only
- Limit file length to 300 lines

## Comments and Documentation

### Comment Policy
- Code should be self-documenting
- Avoid obvious comments: `# increment counter` for `counter += 1`
- Use comments only for complex business logic
- No docstrings for simple, self-explanatory functions
- Document public APIs and complex algorithms only

### When to Comment
- Complex business rules
- Performance optimizations
- Workarounds for external library bugs
- Regular expressions
- Complex mathematical formulas

## Data Structures

### Prefer Modern Python
- Use f-strings over `.format()` or `%` formatting
- Use list/dict comprehensions for simple transformations
- Use dataclasses instead of regular classes for data containers
- Use type hints for function signatures
- Use `pathlib` instead of `os.path`

### Collections
- Use appropriate data structures: `set` for uniqueness, `deque` for queues
- Prefer `dict.get()` over `dict[key]` when key might not exist
- Use `collections.defaultdict` when appropriate

## Django/Celery Specific

### Models
- Keep models focused and cohesive
- Use model managers for complex queries
- Avoid business logic in models (use services)
- Use `select_related` and `prefetch_related` appropriately

### Views
- Keep views thin - delegate to services
- Use class-based views for complex logic
- Validate input early
- Return appropriate HTTP status codes

### Celery Tasks
- Keep tasks idempotent when possible
- Use explicit task names
- Handle task failures gracefully
- Avoid long-running tasks (break into smaller chunks)

## Performance Guidelines

### Database
- Use `bulk_create` for multiple inserts
- Avoid N+1 queries
- Use database indexes appropriately
- Consider pagination for large datasets

### Memory Management
- Use generators for large datasets
- Close file handles and database connections
- Avoid loading entire datasets into memory

## Code Patterns

### Preferred Patterns
```python
# Good: Early return
def process_user(user_id):
    if not user_id:
        return None
    
    user = get_user(user_id)
    if not user.is_active:
        return None
    
    return user.process()

# Good: Context manager
with get_database_connection() as conn:
    result = conn.execute(query)

# Good: List comprehension
active_users = [user for user in users if user.is_active]
```

### Avoid These Patterns
```python
# Bad: Deep nesting
def bad_function():
    if condition1:
        if condition2:
            if condition3:
                # Too deep

# Bad: Long parameter list
def bad_function(a, b, c, d, e, f, g):
    pass

# Bad: Unclear naming
def calc(d):  # What does this calculate?
    return d * 2
```

## Testing

### Test Naming
- Use descriptive test names: `test_user_creation_with_valid_email`
- Group related tests in classes
- Use `setUp` and `tearDown` appropriately

### Test Structure
- Arrange, Act, Assert pattern
- One assertion per test when possible
- Use fixtures for common test data
- Mock external dependencies

## Error Messages

### User-Facing Errors
- Use clear, actionable error messages
- Include context when helpful
- Avoid technical jargon for end users

### Developer Errors
- Include relevant context in exception messages
- Use logging for debugging information
- Include stack traces for unexpected errors

## Logging

### Log Levels
- DEBUG: Detailed diagnostic information
- INFO: General information about program execution
- WARNING: Something unexpected happened
- ERROR: A serious problem occurred
- CRITICAL: The program may not be able to continue

### Log Content
- Include relevant context (user_id, request_id, etc.)
- Use structured logging when possible
- Avoid logging sensitive information

## Security

### Input Validation
- Validate all user inputs
- Use parameterized queries
- Sanitize data before display
- Use HTTPS for sensitive data

### Authentication/Authorization
- Check permissions at appropriate levels
- Use Django's built-in security features
- Hash passwords properly
- Implement rate limiting for APIs

## Git Commit Messages

### Format
```
type(scope): brief description

Longer explanation if needed

- List specific changes
- Reference issue numbers
```

### Types
- feat: New feature
- fix: Bug fix
- refactor: Code refactoring
- docs: Documentation changes
- test: Adding tests
- style: Code formatting changes

## Code Review Checklist

- [ ] Follows naming conventions
- [ ] Functions are small and focused
- [ ] No unnecessary comments
- [ ] Error handling is appropriate
- [ ] Tests cover new functionality
- [ ] No hardcoded values
- [ ] Imports are organized
- [ ] Type hints are used
- [ ] Performance considerations addressed
- [ ] Security implications considered
- [ ] Do not write any comment
