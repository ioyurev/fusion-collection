from configparser import ConfigParser

from loguru import logger as log

CONFIG_PATH = "config.ini"


class Config(ConfigParser):
    is_test_mode = False
    recent_operator = ""

    def write(self):
        log.debug("Запись конфигурационного файла.")
        self.set("Settings", "is_test_mode", f"{self.is_test_mode}")
        self.set("Recent", "operator", self.recent_operator)
        with open(CONFIG_PATH, "w", encoding="utf-8") as configfile:
            super().write(configfile)

    def make_defaults(self):
        self.add_section("Settings")
        self.add_section("Recent")
        self.write()

    def read(self):
        log.debug("Чтение конфигурационного файла.")
        super().read(CONFIG_PATH, encoding="utf-8")

        if len(self.sections()) == 0:
            log.warning("Конфигурационного файла не существует. Создание по умолчанию.")
            self.make_defaults()

        self.is_test_mode = self.getboolean("Settings", "is_test_mode")
        self.recent_operator = self.get("Recent", "operator")

        if self.is_test_mode:
            log.warning("Включен тестовый режим.")
        log.debug(f"Последний оператор: {self.recent_operator}")


config = Config()
config.read()
