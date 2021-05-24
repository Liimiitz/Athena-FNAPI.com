import json
import locale
import logging
import requests
import coloredlogs
from datetime import date
from PIL import Image, ImageFont

log = logging.getLogger(__name__)
coloredlogs.install(level="INFO", fmt="[%(asctime)s] %(message)s", datefmt="%I:%M:%S")


class ConfgFile:
    language: str = "en"
    send_on_start: bool = False

    api_key: str = None
    support_a_creator: str = None

    twitter_enabled: bool = False
    twitter_api_key: str = None
    twitter_api_secret: str = None
    twitter_access_token: str = None
    twitter_access_secret: str = None

    def __init__(self) -> None:
        log.info("Configuration file => Initialized")

    def load_config(self) -> bool:
        """
        Set the configuration values specified in configuration.json
        Return True if configuration sucessfully loaded.
        """
        try:
            with open("configuration.json", "r", encoding="utf-8") as data:
                configuration = json.load(data)

            self.language = configuration.get("language", "en")
            self.send_on_start = configuration.get("sendOnStart", False)

            self.api_key = configuration.get("fortniteAPI", {}).get("apiKey")
            self.support_a_creator = configuration.get("supportACreator")

            twitter_data = configuration.get("twitter", {})
            self.twitter_enabled = twitter_data.get("enabled", False)
            self.twitter_api_key = twitter_data.get("apiKey")
            self.twitter_api_secret = twitter_data.get("apiSecret")
            self.twitter_access_token = twitter_data.get("accessToken")
            self.twitter_access_secret = twitter_data.get("accessSecret")

            log.info("Configuration file => Loaded")
            return True
        except Exception as e:
            log.critical(f"Configuration file => Failed to load => {e}")
        return False


class APITracker:
    API_URL = "https://fortnite-api.com/v2/shop/br/combined"
    api_key: str = None
    language: str = None
    last_hash: str = None

    def __init__(self, api_key: str, language: str = "en") -> None:
        self.api_key = api_key
        self.language = language

    def get_itemshop(self) -> dict:
        """
        Return the response of a successful HTTP GET request to the specified
        URL with the optionally provided header values.
        """
        response = requests.get(
            self.API_URL,
            headers={"x-api-key": self.api_key},
            params={"language": self.language}
        )
        if response.status_code == 200:
            return response.json()

        log.error(f"API Tracker => Status code {response.status_code}")
        return None

    def update_hash(self, new_hash: str) -> None:
        self.last_hash = new_hash

    def initial_load(self) -> bool:
        response = self.get_itemshop()
        if response is not None:
            self.update_hash(response.get("data", {}).get("hash"))
            return True
        return False

    def get_update(self) -> tuple:
        response = self.get_itemshop()
        if response is not None:
            new_hash = response.get("data", {}).get("hash")
            if new_hash != self.last_hash:
                return new_hash, response
        return None, response


class ImageUtility:
    """Class containing utilitarian image-based functions intended to reduce duplicate code."""

    @staticmethod
    def open(filename: str, directory: str = "assets/images/") -> Image.Image:
        """Return the specified image file."""
        try:
            return Image.open(f"{directory}{filename}")
        except Exception as error:
            log.error(f"ImageUtility.open => {error}")
        return None

    @staticmethod
    def download(url: str) -> Image.Image:
        """Download and return the raw file from the specified url as an image object."""
        try:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                return Image.open(response.raw).convert("RGBA")
            log.error(f"ImageUtility.download => HTTP {response.status_code} => Faild to get {url}")
        except Exception as error:
            log.error(f"ImageUtility.download => {error} => Faild to get {url}")
        return None

    @staticmethod
    def resize(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
        """Resize and return the provided image while maintaining aspect ratio."""
        ratio = max(max_width / image.width, max_height / image.height)
        return image.resize((int(image.width * ratio), int(image.height * ratio)), Image.ANTIALIAS)

    @staticmethod
    def align_center(foreground_width: int, background_width: int, distanceTop: int = 0):
        """Return the tuple necessary for horizontal centering and an optional vertical distance."""
        return ((background_width - foreground_width)//2, distanceTop)

    @staticmethod
    def font(size: int, font: str = "BurbankBigRegular-Black.ttf", directory: str = "assets/fonts/"):
        """Return a font object with the specified font file and size."""
        try:
            return ImageFont.truetype(f"{directory}{font}", size)
        except OSError:
            log.warn("ImageUtil => BurbankBigRegular-Black.ttf not found, defaulted font to LuckiestGuy-Regular.ttf")

            return ImageFont.truetype(f"{directory}LuckiestGuy-Regular.ttf", size)
        except Exception as error:
            log.error(f"ImageUtil => Failed to load font, {error}")

    def fit_text(self, text: str, size: int, max_size: int, font: str = "BurbankBigRegular-Black.ttf"):
        """Return the font and width which fits the provided text within the specified maxiumum width."""
        change = 0
        font = self.font(size)
        text_width, _ = font.getsize(text)

        while text_width >= max_size:
            size -= 1
            change += 1
            font = self.font(size)
            text_width, _ = font.getsize(text)

        return font, text_width, change


def get_date(language: str):
    """Return the provided ISO8601 timestamp in human-readable format."""
    today = date.today()

    try:
        locale.setlocale(locale.LC_ALL, language)
    except locale.Error:
        log.warn(f"ISO to Human => Unsupported locale configured, using system default")

    try:
        # Unix-supported zero padding removal
        return today.strftime("%-d %B %Y")
    except ValueError:
        # Windows-supported zero padding removal
        return today.strftime("%#d %B %Y")
    except Exception as error:
        log.error(f"ISO to Human => Failed to convert to human-readable time: {error}")
