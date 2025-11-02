# main.py

import logging

from gui.start import launch


def init_logger(log_file="log/app.log"):
    """Configures the logger to write to a file."""

    log_format = "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s"
    date_format = "%d-%m-%Y %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        filename=log_file,
        filemode="a",
    )


def main():

    init_logger()

    launch()


if __name__ == "__main__":
    main()
