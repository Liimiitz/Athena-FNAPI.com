import json
import logging
from sys import exit
from math import ceil
from time import sleep
from datetime import date

import twitter
import coloredlogs
from PIL import Image, ImageDraw

from util import ImageUtil, Utility

log = logging.getLogger(__name__)
coloredlogs.install(level="INFO", fmt="[%(asctime)s] %(message)s", datefmt="%I:%M:%S")


class Athena:
    """Fortnite Item Shop Generator."""
    utility = Utility()
    itemshop_hash: str = None

    def __init__(self) -> None:
        print("Athena - Fortnite Item Shop Generator")
        print("https://github.com/Liimiitz/Athena-FNAPI.com\n")

        if self.LoadConfiguration():
            # Update hashes on first load if sendOnStart was disabled
            if not self.sendOnStart:
                itemshop = self.fetch_itemshop_data()
                if len(itemshop.keys()) > 0:
                    self.itemshop_hash = itemshop.get("hash")
                    log.info(f"Hashes updated. New hash code is {self.itemshop_hash}")
                else:
                    return

            # infinite loop to get updates every X second and update files on shop change
            while True:
                itemshop = self.fetch_itemshop_data()
                if len(itemshop.keys()) > 0 and self.itemshop_hash != itemshop.get("hash"):
                    # Strip time from the timestamp, we only need the date
                    today_date = self.utility.ISOtoHuman(date.today(), self.language)
                    log.info(f"Retrieved Item Shop for {today_date}")

                    if self.GenerateImage(today_date, itemshop):
                        self.itemshop_hash = itemshop.get("hash")
                        if self.twitterEnabled:
                            self.Tweet(today_date)
                else:
                    log.info("Data checked, nothing was changed.")

                sleep(self.checkForUpdates)

    def fetch_itemshop_data(self) -> dict:
        itemshop = self.utility.get_itemshop(self.language)
        if itemshop.status_code == 200:
            return itemshop.json().get("data", {})
        else:
            log.critical(f"Failed to GET ItemShop (HTTP {itemshop.status_code})")
            return {}

    def LoadConfiguration(self) -> bool:
        """
        Set the configuration values specified in configuration.json

        Return True if configuration sucessfully loaded.
        """

        configuration = json.loads(self.utility.ReadFile("configuration", "json"))

        try:
            # self.delay = configuration.get("delayStart", 0)
            self.language = configuration.get("language", "en")
            self.sendOnStart = configuration.get("sendOnStart", False)
            self.checkForUpdates = configuration.get("checkForUpdates", 10)
            self.supportACreator = configuration.get("supportACreator")

            twitter_data = configuration.get("twitter", {})
            self.twitterEnabled = twitter_data.get("enabled", False)
            self.twitterAPIKey = twitter_data.get("apiKey")
            self.twitterAPISecret = twitter_data.get("apiSecret")
            self.twitterAccessToken = twitter_data.get("accessToken")
            self.twitterAccessSecret = twitter_data.get("accessSecret")

            log.info("Loaded configuration")

            return True
        except Exception as e:
            log.critical(f"Failed to load configuration, {e}")

        return False

    def GenerateImage(self, date: str, itemShop: dict):
        """
        Generate the Item Shop image using the provided Item Shop.

        Return True if image sucessfully saved.
        """

        try:
            featured = itemShop["featured"]["entries"]
            daily = itemShop["daily"]["entries"]

            if (len(featured) <= 0) or (len(daily) <= 0):
                raise Exception(
                    f"Featured: {len(featured)}, Daily: {len(daily)}")

            if (len(featured) >= 1):
                width = 6
                height = max(ceil(len(featured) / 3), ceil(len(daily) / 3))

                rowsDaily = 3
                rowsFeatured = 3

                dailyStartX = ((340 * 3))

            if (len(featured) >= 18):
                width = 9
                height = max(ceil(len(featured) / 6), ceil(len(daily) / 6))

                rowsDaily = 3
                rowsFeatured = 6

                dailyStartX = ((340 * 6))

            if (len(featured) >= 18) and (len(daily) >= 18):
                width = 12
                height = max(ceil(len(featured) / 6), ceil(len(daily) / 6))

                rowsDaily = 6
                rowsFeatured = 6

                dailyStartX = ((340 * 6) + 100)

        except Exception as e:
            log.critical(f"Failed to parse Item Shop Featured and Daily items, {e}")
            return False

        # Determine the max amount of rows required for the current
        # Item Shop when there are 3 columns for both Featured and Daily.
        # This allows us to determine the image height.

        shopImage = Image.new("RGB", (((340 * width) - 30), (530 * height) + 350))

        try:
            background = ImageUtil.Open(self, "background.png")
            background = ImageUtil.RatioResize(
                self, background, shopImage.width, shopImage.height
            )
            shopImage.paste(
                background, ImageUtil.CenterX(
                    self, background.width, shopImage.width)
            )
        except FileNotFoundError:
            log.warning(
                "Failed to open background.png, defaulting to dark gray")
            shopImage.paste(
                (34, 37, 40), [0, 0, shopImage.size[0], shopImage.size[1]])

        canvas = ImageDraw.Draw(shopImage)
        font = ImageUtil.Font(self, 80)

        textWidth, _ = font.getsize("FORTNITE ITEM SHOP")
        canvas.text(ImageUtil.CenterX(self, textWidth, shopImage.width, 30), "FORTNITE ITEM SHOP", (255, 255, 255), font=font)
        textWidth, _ = font.getsize(date.upper())
        canvas.text(ImageUtil.CenterX(self, textWidth, shopImage.width, 120), date.upper(), (255, 255, 255), font=font)

        if itemShop["featured"] is not None:
            canvas.text((20, 240), "FEATURED", (255, 255, 255), font=font, anchor=None, spacing=4, align="left")

        if itemShop["daily"] is not None:
            canvas.text((shopImage.width - 230, 240), "DAILY", (255, 255, 255), font=font, anchor=None, spacing=4, align="right")

        # Track grid position
        i = 0

        for item in featured:
            card = Athena.GenerateCard(self, item)

            if card is not None:
                shopImage.paste(
                    card,
                    (
                        (20 + ((i % rowsFeatured) * (310 + 20))),
                        (350 + ((i // rowsFeatured) * (510 + 20))),
                    ),
                    card,
                )

                i += 1

        # Reset grid position
        i = 0

        for item in daily:
            card = Athena.GenerateCard(self, item)

            if card is not None:
                shopImage.paste(
                    card,
                    (
                        (dailyStartX + ((i % rowsDaily) * (310 + 20))),
                        (350 + ((i // rowsDaily) * (510 + 20))),
                    ),
                    card,
                )

                i += 1

        try:
            shopImage.save("itemshop.jpeg", optimize=True, quality=85)
            log.info("Generated Item Shop image")

            return True
        except Exception as e:
            log.critical(f"Failed to save Item Shop image, {e}")

    def GenerateCard(self, item: dict):
        """Return the card image for the provided Fortnite Item Shop item."""

        try:
            name = item["items"][0]["name"].lower()
            rarity = item["items"][0]["rarity"]["value"].lower()
            category = item["items"][0]["type"]["value"].lower()
            price = item["finalPrice"]

            if (item["items"][0]["images"]["featured"]):
                icon = item["items"][0]["images"]["featured"]
            else:
                icon = item["items"][0]["images"]["icon"]

            if(item["bundle"]):
                icon = item["bundle"]["image"]
                name = item["bundle"]["name"].lower()
                category = "Bundle".lower()
        except Exception as e:
            log.error(f"Failed to parse item {name}, {e}")

            return

        if rarity == "frozen":
            blendColor = (148, 223, 255)
        elif rarity == "lava":
            blendColor = (234, 141, 35)
        elif rarity == "legendary":
            blendColor = (211, 120, 65)
        elif rarity == "slurp":
            blendColor = (0, 233, 176)
        elif rarity == "dark":
            blendColor = (251, 34, 223)
        elif rarity == "starwars":
            blendColor = (231, 196, 19)
        elif rarity == "marvel":
            blendColor = (197, 51, 52)
        elif rarity == "dc":
            blendColor = (84, 117, 199)
        elif rarity == "icon":
            blendColor = (54, 183, 183)
        elif rarity == "shadow":
            blendColor = (113, 113, 113)
        elif rarity == "gaminglegends":
            blendColor = (117, 129, 209)
            rarity = "GamingLegends"
        elif rarity == "epic":
            blendColor = (177, 91, 226)
        elif rarity == "rare":
            blendColor = (73, 172, 242)
        elif rarity == "uncommon":
            blendColor = (96, 170, 58)
        elif rarity == "common":
            blendColor = (190, 190, 190)
        else:
            blendColor = (255, 255, 255)

        card = Image.new("RGBA", (310, 510))

        try:
            layer = ImageUtil.Open(
                self, f"./shopTemplates/{rarity.capitalize()}BG.png")
        except FileNotFoundError:
            log.warn(
                f"Failed to open {rarity.capitalize()}BG.png, defaulted to Common")
            layer = ImageUtil.Open(self, "./shopTemplates/CommonBG.png")
        card.paste(layer)

        icon = ImageUtil.Download(self, icon)
        if (category == "outfit") or (category == "emote"):
            icon = ImageUtil.RatioResize(self, icon, 285, 365)
        elif category == "wrap":
            icon = ImageUtil.RatioResize(self, icon, 230, 310)
        else:
            icon = ImageUtil.RatioResize(self, icon, 310, 390)
        if (category == "outfit") or (category == "emote"):
            card.paste(icon, ImageUtil.CenterX(self, icon.width, card.width), icon)
        else:
            card.paste(icon, ImageUtil.CenterX(self, icon.width, card.width, 15), icon)

        try:
            layer = ImageUtil.Open(
                self, f"./shopTemplates/{rarity.capitalize()}OV.png")
        except FileNotFoundError:
            log.warn(
                f"Failed to open {rarity.capitalize()}OV.png, defaulted to Common")
            layer = ImageUtil.Open(self, "./shopTemplates/CommonOV.png")

        card.paste(layer, layer)

        canvas = ImageDraw.Draw(card)

        vbucks = ImageUtil.Open(self, "vbucks.png")
        vbucks = ImageUtil.RatioResize(self, vbucks, 40, 40)

        font = ImageUtil.Font(self, 40)
        price = str(f"{price:,}")
        textWidth, _ = font.getsize(price)

        canvas.text(ImageUtil.CenterX(self, ((textWidth - 5) - vbucks.width), card.width, 347), price, (255, 255, 255), font=font)
        card.paste(vbucks, ImageUtil.CenterX(self, (vbucks.width + (textWidth + 5)), card.width, 350), vbucks)

        font = ImageUtil.Font(self, 40)
        itemName = name.upper().replace(" OUTFIT", "").replace(" PICKAXE", "").replace(" BUNDLE", "")

        if(category == "bundle"):
            itemName = name.upper().replace(" BUNDLE", "")

        textWidth, _ = font.getsize(itemName)

        change = 0
        if textWidth >= 280:
            # Ensure that the item name does not overflow
            font, textWidth, change = ImageUtil.FitTextX(self, itemName, 40, 260)
        canvas.text(ImageUtil.CenterX(self, textWidth, card.width, (400 + (change / 2))), itemName, (255, 255, 255), font=font)

        font = ImageUtil.Font(self, 40)
        textWidth, _ = font.getsize(f"{category.upper()}")

        change = 0
        if textWidth >= 280:
            # Ensure that the item rarity/type does not overflow
            font, textWidth, change = ImageUtil.FitTextX(self, f"{category.upper()}", 40, 260)
        canvas.text(ImageUtil.CenterX(self, textWidth, card.width, (450 + (change / 2))), f"{category.upper()}", blendColor, font=font)
        return card

    def Tweet(self, date: str):
        """
        Tweet the current `Item Shop` image to Twitter using the credentials provided
        in `configuration.json`.
        """

        try:
            twitterAPI = twitter.Api(
                consumer_key=self.twitterAPIKey,
                consumer_secret=self.twitterAPISecret,
                access_token_key=self.twitterAccessToken,
                access_token_secret=self.twitterAccessSecret,
            )

            twitterAPI.VerifyCredentials()

        except Exception as e:
            log.critical(f"Failed to authenticate with Twitter, {e}")

            return

        body = f"Battle Royale - #Fortnite Item Shop | {date}"

        if self.supportACreator is not None:
            body = f"{body}\n\nUse code: {self.supportACreator} in the item shop!"

        try:

            with open("itemshop.jpeg", "rb") as shopImage:
                twitterAPI.PostUpdate(body, media=shopImage)

            log.info("Tweeted Item Shop")
        except Exception as e:
            log.critical(f"Failed to Tweet Item Shop, {e}")


if __name__ == "__main__":
    try:
        Athena()
    except KeyboardInterrupt:
        log.info("Exiting...")
        exit()
