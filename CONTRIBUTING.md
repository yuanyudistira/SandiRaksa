# Contributing to SandiRaksa

Thank you for your interest in contributing to SandiRaksa! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- (Optional) Virtual environment tool (venv, conda, etc.)

### Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/sandiraksa.git
   cd sandiraksa
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   .\venv\Scripts\activate  # Windows
   ```

3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Download required NLP model:
   ```bash
   python -m spacy download en_core_web_sm
   ```

5. Run tests to verify setup:
   ```bash
   pytest tests/unit -v
   ```

## Development Workflow

### Branching Strategy

- `main`: Stable release branch
- `develop`: Integration branch for features
- `feature/xxx`: Feature branches
- `bugfix/xxx`: Bug fix branches
- `hotfix/xxx`: Critical fixes for production

### Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the coding standards

3. Run linting:
   ```bash
   ruff check src/ tests/
   ruff format src/ tests/
   ```

4. Run tests:
   ```bash
   pytest tests/ -v
   ```

5. Commit your changes:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

6. Push and create a Pull Request

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use Ruff for linting and formatting

### Testing

- Write tests for all new features
- Maintain test coverage above 80%
- Include unit, integration, and security tests where appropriate

## Pull Request Process

1. Update documentation if needed
2. Add tests for new functionality
3. Ensure all tests pass
4. Update CHANGELOG.md if applicable
5. Request review from maintainers

## Reporting Issues

When reporting issues, please include:

1. Description of the issue
2. Steps to reproduce
3. Expected vs actual behavior
4. System information (OS, Python version)
5. Relevant logs or error messages

## Security Issues

For security vulnerabilities, please email security@sandiraksa.example.com instead of creating a public issue.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## Questions?

Feel free to open a discussion or reach out to the maintainers.

Thank you for contributing! 🙏
