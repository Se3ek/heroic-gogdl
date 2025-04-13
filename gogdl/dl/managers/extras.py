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

        if "path" in self.arguments:
            self.path = self.arguments.path     # Path for download
        else:
            self.path = ""
        if "support_path" in self.arguments:
            self.support = self.arguments.support_path
        else:
            self.support = ""

        self.allowed_threads = generic_manager.allowed_threads

        self.api_handler: ApiHandler = generic_manager.api_handler
        self.stop_all_threads = False

        self.logger = logging.getLogger("extras")
        self.logger.info("Initialized extras Download Manager")

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

    def download(self):
        # Get all the links that are available
        game_info: dict = self.api_handler.get_game_details(self.game_id)

        self.logger.info(f"Downloading additional files for game {game_info["title"]} (id {self.game_id})")

        # build a list of urls for the downloads
        urls: list[str] = []

        if self.arguments.installers:
            # Get the specified platforms. Otherwise, take all of them

            lang: str = self.arguments.language
            platform_content: dict = dict()
            for element in game_info["downloads"]:
                if not element[0] == lang:
                    continue
                for plat in element[1]:
                    if not plat == self.platform:
                        continue
                    if not platform_content.get(plat):
                        if self.patches:
                            platform_content[plat] = [c for c in element[1][plat] if c["name"].startswith("Patch ")]
                        else:
                            platform_content[plat] = [c for c in element[1][plat] if not c["name"].startswith("Patch ")]
                    else:
                        if self.patches:
                            platform_content[plat].extend([c for c in element[1][plat] if c["name"].startswith("Patch ")])
                        else:
                            platform_content[plat].extend([c for c in element[1][plat] if not c["name"].startswith("Patch ")])

            for platform in platform_content:
                urls.extend([f"{constants.GOG_EMBED}/{dl["manualUrl"]}" for dl in platform_content[platform]])

        urls.extend([f"{constants.GOG_EMBED}/{extra["manualUrl"]}" for extra in game_info["extras"]])

        self.logger.info(f"There are {len(urls)} extras...")

        if self.dry_run:
            for url in urls:
                with self.api_handler.session.get(url, stream=True) as response:
                    filename: str = response.url.split("/")[-1]

                num, sym = get_readable_size(int(response.headers["Content-Length"]))
                self.logger.info(f"Would download: {filename}, size: {num:.1f} {sym}")
            return
        with ThreadPoolExecutor(max_workers=self.allowed_threads) as ex:
            ex.map(self.download_file, urls)
