import time
import twitter
import logging
import coloredlogs
from math import ceil
from PIL import Image, ImageDraw
from utilty import ConfgFile, APITracker, ImageUtility, get_date

log = logging.getLogger(__name__)
coloredlogs.install(level="INFO", fmt="[%(asctime)s] %(message)s", datefmt="%I:%M:%S")


class Athena:
    config: ConfgFile
    tracker: APITracker
    image_utility: ImageUtility

    def __init__(self) -> None:
        log.info("<  Athena - Fortnite Item Shop Generator   >")
        log.info("<      Forked from: Github => @EthanC      >")
        log.info("< Contributed by: Liimiitz & MR-AliHaashemi>")
        log.info("< https://github.com/Liimiitz/Athena-FNAPI.com >")

        self.config = ConfgFile()
        if not self.config.load_config():
            return
        self.tracker = APITracker(self.config.api_key, self.config.language)
        self.image_utility = ImageUtility()

        self.check_for_initial_load()
        self.track_updates()

    def check_for_initial_load(self):
        if not self.config.send_on_start:
            is_loaded = self.tracker.initial_load()
            # Just to make sure it's loaded
            while not is_loaded:
                log.error("Athena => Initial load faild, trying again in 5 seconds...")
                time.sleep(5)
                is_loaded = self.tracker.initial_load()
            log.info("Athena => Initial load => Done.")

    def track_updates(self):
        log.info("Athena => Tracker started! Waiting for updates...")
        while True:
            # try:
            new_hash, data = self.tracker.get_update()
            if new_hash is not None:
                date = get_date(self.config.language)
                log.info(f"Athena => Update detected => hash: {new_hash}")
                log.info(f"Athena => Generating image for {date}")
                start = time.time_ns()
                if self.generate_image(date, data.get("data", {})):
                    log.info(f"Athena => Image Generated in => {((time.time_ns()-start)/1000000000)}")

                    if self.config.twitter_enabled:
                        log.info("Athena => Sending image to twitter...")
                        start = time.time_ns()
                        self.tweet_image(date)
                        log.info(f"Athena => Image Sent in => {((time.time_ns()-start)/1000000000)}\n")

                    self.tracker.update_hash(new_hash)
                    log.info("Athena => Waiting for new updates...")
            # except Exception as error:
            #     log.error(
            #         f"Athena => Error occured => {error}\n"
            #         "Athena => Report this error + more details to developers.\n"
            #         "Discord => Liimiitz#1538\n"
            #         "Discord => Ali Hashemi#2201\n"
            #     )

            time.sleep(15)

    def generate_image(self, date: str, itemshop: dict) -> bool:
        """
        Generate the Item Shop image using the provided Item Shop.

        Return True if image sucessfully saved.
        """
        try:
            featured = itemshop["featured"]["entries"]
            daily = itemshop["daily"]["entries"]

            if (len(featured) <= 0) and (len(daily) <= 0):
                log.error(f"ImageGeneration => Featured: {len(featured)}, Daily: {len(daily)}")
                return False

            if (len(featured) >= 18) and (len(daily) >= 18):
                width = 12
                height = max(ceil(len(featured) / 6), ceil(len(daily) / 6))

                rowsDaily = 6
                rowsFeatured = 6

                dailyStartX = ((340 * 6) + 100)
            elif len(featured) >= 18:
                width = 9
                height = max(ceil(len(featured) / 6), ceil(len(daily) / 6))

                rowsDaily = 3
                rowsFeatured = 6

                dailyStartX = ((340 * 6))
            else:  # len(featured) >= 1
                width = 6
                height = max(ceil(len(featured) / 3), ceil(len(daily) / 3))

                rowsDaily = 3
                rowsFeatured = 3

                dailyStartX = ((340 * 3))
        except Exception as error:
            log.critical(f"ImageGeneration => Failed to parse Item Shop Featured and Daily items, {error}")
            return False

        # Determine the max amount of rows required for the current
        # Item Shop when there are 3 columns for both Featured and Daily.
        # This allows us to determine the image height.
        shopImage = Image.new("RGB", (((340 * width) - 30), (530 * height) + 350))

        background = self.image_utility.open("background.png")
        if background is not None:
            background = self.image_utility.resize(background, shopImage.width, shopImage.height)
            shopImage.paste(background, self.image_utility.align_center(background.width, shopImage.width))
        else:
            log.warning("ImageGeneration => Failed to open background.png, defaulting to dark gray")
            shopImage.paste((34, 37, 40), [0, 0, shopImage.width, shopImage.height])

        canvas = ImageDraw.Draw(shopImage)
        font = self.image_utility.font(80)

        textWidth, _ = font.getsize("FORTNITE ITEM SHOP")
        canvas.text(self.image_utility.align_center(textWidth, shopImage.width, 30), "FORTNITE ITEM SHOP", (255, 255, 255), font=font)
        textWidth, _ = font.getsize(date.upper())
        canvas.text(self.image_utility.align_center(textWidth, shopImage.width, 120), date.upper(), (255, 255, 255), font=font)

        canvas.text((20, 240), "FEATURED", (255, 255, 255), font=font, anchor=None, spacing=4, align="left")
        canvas.text((shopImage.width - 230, 240), "DAILY", (255, 255, 255), font=font, anchor=None, spacing=4, align="right")

        for index, item in enumerate(featured):
            card = self.generate_card(item)
            if card is not None:
                shopImage.paste(
                    card,
                    (
                        (20 + ((index % rowsFeatured) * (310 + 20))),
                        (350 + ((index // rowsFeatured) * (510 + 20))),
                    ),
                    card,
                )

        for index, item in enumerate(daily):
            card = self.generate_card(item)
            if card is not None:
                shopImage.paste(
                    card,
                    (
                        (dailyStartX + ((index % rowsDaily) * (310 + 20))),
                        (350 + ((index // rowsDaily) * (510 + 20))),
                    ),
                    card,
                )

        try:
            shopImage.save("itemshop.jpeg", optimize=True, quality=85)
            return True
        except Exception as error:
            log.critical(f"ImageGeneration => Failed to save Item Shop image => {error}")
        return False

    def generate_card(self, item: dict) -> Image.Image:
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
        except Exception as error:
            log.error(f"CardGeneration => Failed to parse item {name} => {error}")
            return None

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

        layer = self.image_utility.open(f"shopTemplates/{rarity.capitalize()}BG.png")
        if layer is None:
            log.warn(f"CardGeneration => Failed to open {rarity.capitalize()}BG.png, defaulted to Common")
            layer = self.image_utility.open("shopTemplates/CommonBG.png")
        card.paste(layer)

        icon = self.image_utility.download(icon)
        if icon is not None:
            if (category == "outfit") or (category == "emote"):
                icon = self.image_utility.resize(icon, 285, 365)
            elif category == "wrap":
                icon = self.image_utility.resize(icon, 230, 310)
            else:
                icon = self.image_utility.resize(icon, 310, 390)
            if (category == "outfit") or (category == "emote"):
                card.paste(icon, self.image_utility.align_center(icon.width, card.width), icon)
            else:
                card.paste(icon, self.image_utility.align_center(icon.width, card.width, 15), icon)

        layer = self.image_utility.open(f"shopTemplates/{rarity.capitalize()}OV.png")
        if layer is None:
            log.warn(f"CardGeneration => Failed to open {rarity.capitalize()}OV.png, defaulted to Common")
            layer = self.image_utility.open("shopTemplates/CommonOV.png")
        card.paste(layer, layer)

        canvas = ImageDraw.Draw(card)

        vbucks = self.image_utility.resize(
            self.image_utility.open("vbucks.png"),
            40, 40
        )

        font = self.image_utility.font(40)
        price = str(f"{price:,}")
        textWidth, _ = font.getsize(price)

        canvas.text(self.image_utility.align_center(((textWidth - 5) - vbucks.width), card.width, 347), price, (255, 255, 255), font=font)
        card.paste(vbucks, self.image_utility.align_center((vbucks.width + (textWidth + 5)), card.width, 350), vbucks)

        itemName = name.upper().replace(" OUTFIT", "").replace(" PICKAXE", "").replace(" BUNDLE", "")
        if category == "bundle":
            itemName = name.upper().replace(" BUNDLE", "")

        font, text_width, change = self.image_utility.fit_text(itemName, 40, 260)
        canvas.text(self.image_utility.align_center(text_width, card.width, (400 + (change / 2))), itemName, (255, 255, 255), font=font)

        categoryName = category.upper()
        font, text_width, change = self.image_utility.fit_text(categoryName, 40, 260)
        canvas.text(self.image_utility.align_center(text_width, card.width, (450 + (change / 2))), categoryName, blendColor, font=font)
        return card

    def tweet_image(self, date: str):
        """
        Tweet the current `Item Shop` image to Twitter using the credentials provided
        in `configuration.json`.
        """

        try:
            twitterAPI = twitter.Api(
                consumer_key=self.config.twitter_api_key,
                consumer_secret=self.config.twitter_api_secret,
                access_token_key=self.config.twitter_access_token,
                access_token_secret=self.config.twitter_access_secret,
            )

            twitterAPI.VerifyCredentials()

        except Exception as e:
            log.critical(f"Failed to authenticate with Twitter, {e}")

            return

        body = f"Battle Royale - #Fortnite Item Shop | {date}"

        if self.config.support_a_creator is not None:
            body = f"{body}\n\nUse code: {self.config.support_a_creator} in the item shop!"

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
        log.info("CTRL + C Received >> Exiting...")
        exit(0)
