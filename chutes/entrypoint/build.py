import re
import os
import sys
import shutil
import importlib
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from loguru import logger
from chutes.image.directive.add import ADD
from chutes.image.directive.generic_run import RUN
from chutes.entrypoint._shared import load_chute


CLI_ARGS = {
    "--config-path": {
        "type": str,
        "default": None,
        "help": "custom path to the parachutes config (credentials, API URL, etc.)",
    },
    "--local": {
        "action": "store_true",
        "help": "build the image locally, useful for testing/debugging",
    },
    "--debug": {
        "action": "store_true",
        "help": "enable debug logging",
    },
    "--include-cwd": {
        "action": "store_true",
        "help": "include the entire current directory in build context, recursively",
    },
}


@contextmanager
def temporary_build_directory(image):
    """
    Helper to copy the build context files to a build directory.
    """
    # Confirm the context files with the user.
    all_input_files = []
    for directive in image._directives:
        all_input_files += directive._build_context

    samples = all_input_files[:10]
    logger.info(
        f"Found {len(all_input_files)} files to include in build context -- \033[1m\033[4mthese will be uploaded for remote builds!\033[0m"
    )
    for path in samples:
        logger.info(f" {path}")
    if len(samples) != len(all_input_files):
        show_all = input(
            f"\033[93mShowing {len(samples)} of {len(all_input_files)}, would you like to see the rest? (y/n) \033[0m"
        )
        if show_all.lower() == "y":
            for path in all_input_files[:10]:
                logger.info(f" {path}")
    confirm = input("\033[1m\033[4mConfirm submitting build context? (y/n) \033[0m")
    if confirm.lower().strip() != "y":
        logger.error("Aborting!")
        sys.exit(1)

    # Copy all of the context files over to a temp dir (to use for local building or a zip file for remote).
    _clean_path = lambda in_: in_[len(os.getcwd()) + 1 :]
    with tempfile.TemporaryDirectory() as tempdir:
        for path in all_input_files:
            temp_path = os.path.join(tempdir, _clean_path(path))
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            logger.debug(f"Copying {path} to {temp_path}")
            shutil.copy(path, temp_path)
        yield tempdir


def build_local(image):
    """
    Build an image locally, directly with docker (for testing purposes).
    """
    with temporary_build_directory(image) as build_directory:
        dockerfile_path = os.path.join(build_directory, "Dockerfile")
        with open(dockerfile_path, "w") as outfile:
            outfile.write(str(image))
        logger.info(f"Starting build of {dockerfile_path}...")
        os.chdir(build_directory)
        os.execv(
            "/usr/bin/docker",
            ["/usr/bin/docker", "build", "-t", f"{image.name}:{image.tag}", "."],
        )


async def build_remote(image):
    """
    Build an image remotely, that is, package up the build context and ship it
    off to the parachutes API to have it built.
    """
    with temporary_build_directory(image) as build_directory:
        logger.info(f"Packaging up the build directory to upload: {build_directory}")
        output_path = shutil.make_archive(
            os.path.join(build_directory, "chute"), "zip", build_directory
        )
        logger.info(f"Created the build package: {output_path}")
        # XXX upload to API (signed URL via minio?) then subscribe to websocket?


async def build_image(input_args):
    """
    Build an image for the parachutes platform.
    """
    chute, args = load_chute("chutes build", deepcopy(input_args), CLI_ARGS)

    from chutes.chute import ChutePack

    # Get the image reference from the chute.
    chute = chute.chute if isinstance(chute, ChutePack) else chute
    image = chute.image

    # Pre-built?
    if isinstance(image, str):
        logger.error(
            f"You appear to be using a pre-defined/standard image '{image}', no need to build anything!"
        )
        sys.exit(0)

    # XXX check if the image is already built.

    # Always tack on the final directives, which include installing chutes and adding project files.
    image._directives.append(
        RUN("pip install git+https://github.com/jondurbin/chutes.git")
    )
    current_directory = os.getcwd()
    if args.include_cwd:
        image._directives.append(ADD(source=".", dest="/app"))
    else:
        module_name, chute_name = input_args[0].split(":")
        module = importlib.import_module(module_name)
        module_path = os.path.abspath(module.__file__)
        if not module_path.startswith(current_directory):
            logger.error(
                f"You must run the build command from the directory containing your target chute module: {module.__file__} [{current_directory=}]"
            )
            sys.exit(1)
        _clean_path = lambda in_: in_[len(current_directory) + 1 :]
        image._directives.append(
            ADD(
                source=_clean_path(module.__file__),
                dest=f"/app/{_clean_path(module.__file__)}",
            )
        )
        imported_files = [
            os.path.abspath(module.__file__)
            for module in sys.modules.values()
            if hasattr(module, "__file__") and module.__file__
        ]
        imported_files = [
            f
            for f in imported_files
            if f.startswith(current_directory)
            and not re.search(r"(site|dist)-packages", f)
            and f != os.path.abspath(module.__file__)
        ]
        for path in imported_files:
            image._directives.append(
                ADD(
                    source=_clean_path(path),
                    dest=f"/app/{_clean_path(path)}",
                )
            )
    logger.debug(f"Generated Dockerfile:\n{str(image)}")

    # Building locally?
    if args.local:
        return build_local(image)

    # Package up the context and ship it off for building.
    return await build_remote(image)