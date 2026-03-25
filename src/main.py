"""Main entry point for Data Organiser application."""

import logging
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from src.core.config import AppConfig
from src.ui.main_window import MainWindow


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    setup_logging()
    config = AppConfig.load()

    app = QApplication(sys.argv)
    app.setApplicationName("Data Organiser")
    app.setOrganizationName("DataOrganiser")

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
