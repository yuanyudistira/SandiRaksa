"""
SandiRaksa entry point.

This module provides the main entry point for the application.
"""

import sys


def main() -> int:
    """Main entry point for SandiRaksa application."""
    # Import here to avoid circular imports and speed up CLI help
    from sandiraksa.app.application import SandiRaksaApp

    app = SandiRaksaApp(sys.argv)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
