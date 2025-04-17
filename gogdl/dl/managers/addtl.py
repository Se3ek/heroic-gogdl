# Manage downloading extra content (wallpapers, soundtracks, etc.)
import os.path
from concurrent.futures.thread import ThreadPoolExecutor

from gogdl.api import ApiHandler
from gogdl import constants
from gogdl.dl.dl_utils import get_readable_size
import logging


class Manager:
    def __init__(self, generic_manager):
        self.game_id: str = generic_manager.game_id
        self.arguments = generic_manager.arguments
        self.unknown_arguments = generic_manager.unknown_arguments

        self.platform = self.arguments.platform or "windows"

        self.dry_run = self.arguments.dry_run

        self.installers = self.arguments.installers
        self.patches = self.arguments.patches
        self.extras = self.arguments.extras

        self.path = self.arguments.path if "path" in self.arguments else ""

        self.language = self.arguments.language

        self.allowed_threads = generic_manager.allowed_threads

        self.api_handler: ApiHandler = generic_manager.api_handler
        self.stop_all_threads = False

        self.urls = list()  # Empty list for determined urls to be filled later

        self.logger = logging.getLogger("addtl")
        self.logger.info("Initialized additial files Download Manager")

    def download_file(self, url):
        """
        Download a single file from a url
        """
        response = self.api_handler.session.get(url, stream=True)

        filename: str = response.url.split("/")[-1]

        self.logger.info(f"Downloading the file '{filename}'")

        with open(os.path.join(self.path, filename), mode="wb") as file:
            for chunk in response.iter_content(chunk_size=10 * 1024):
                file.write(chunk)

    def run_dry(self, url):
        """
        Get the information from the source for a dry run.
        """
        with self.api_handler.session.get(url, stream=True) as response:
            filename: str = response.url.split("/")[-1]
            num, sym = get_readable_size(int(response.headers["Content-Length"]))

        self.logger.info(f"Would download: {filename}, size: {num:.1f} {sym}")

    def get_urls(self):
        """
        Get the urls for additional content.
        """

        game_info: dict = self.api_handler.get_game_details(self.game_id)

        self.logger.info(f"Downloading additional files for game {game_info["title"]} (id {self.game_id})")

        content: list = list()
        for element in game_info["downloads"]:
            if not element[0] == self.language:     # Filtering out other languages
                continue
            for plat in element[1]:
                if not plat == self.platform:
                    continue
                if self.patches:
                    self.logger.info("Grabbing patches...")
                    content.extend([c for c in element[1][plat] if c["name"].startswith("Patch ")])
                if self.installers:
                    self.logger.info("Grabbing offline installers...")
                    content.extend([c for c in element[1][plat] if not c["name"].startswith("Patch ")])

            self.urls.extend([f"{constants.GOG_EMBED}/{dl["manualUrl"]}" for dl in content])

        if self.extras:
            self.logger.info("Grabbing extra content...")
            self.urls.extend([f"{constants.GOG_EMBED}/{extra["manualUrl"]}" for extra in game_info["extras"]])

    def download(self):
        self.get_urls()

        self.logger.info(f"There are {len(self.urls)} extras...")

        if self.dry_run:
            self.logger.info("In dry run mode...")
            with ThreadPoolExecutor(max_workers=self.allowed_threads) as ex:
                ex.map(self.run_dry, self.urls)
        else:
            with ThreadPoolExecutor(max_workers=self.allowed_threads) as ex:
                ex.map(self.download_file, self.urls)
