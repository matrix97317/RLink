# -*- coding: utf-8 -*-
"""Command Line Interface for RLink."""

import click

from rlinks.learner import RLinkLearner

CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "show_default": True,
}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option()
def cli() -> None:
    """Command Line Interface for RLink."""


@cli.command()
@click.option(
    "-gn",
    "--gpu-num",
    type=int,
    default=1,
    help="Specify the number of GPUs to use.",
)
@click.option(
    "-p",
    "--port",
    type=int,
    default=8443,
    help="Specify the port of HTTP for the distributed communication.",
)
@click.option(
    "-dp",
    "--data-port",
    type=int,
    default=13338,
    help="Specify the port of UCXX for the distributed communication.",
)
def learner(
    gpu_num: int,
    port: int,
    data_port: int,
) -> None:
    """Entry for rlink transmits variables from here."""
    rl_learner = RLinkLearner(
        host="0.0.0.0",
        port=port,
        data_port=data_port,
        data_callback=None,
        gpu_num=gpu_num,
        enable_ucxx=True,
    )
    rl_learner.serve_forever()
