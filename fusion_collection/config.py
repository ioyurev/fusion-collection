from configparser import ConfigParser

from loguru import logger as log

CONFIG_PATH = "config.ini"


class Config(ConfigParser):
    def write(self):
        log.info("Запись конфигурационного файла.")
        with open(CONFIG_PATH, "w", encoding="utf-8") as configfile:
            super().write(configfile)

    def make_defaults(self):
        self.add_section("Settings")
        self.set("Settings", "is_test_mode", "False")
        self.add_section("Recent")
        self.set("Recent", "operator", "")
        self.write()

    def read(self):
        log.info("Чтение конфигурационного файла.")
        super().read(CONFIG_PATH, encoding="utf-8")

        if len(self.sections()) == 0:
            log.info("Конфигурационного файла не существует. Создание по умолчанию.")
            self.make_defaults()
        if self.is_test_mode():
            log.warning("Включен тестовый режим.")

    def get_recent_operator(self):
        return self["Recent"]["operator"]

    def set_recent_operator(self, value):
        self["Recent"]["operator"] = value

    def is_test_mode(self):
        return self.getboolean("Settings", "is_test_mode")


config = Config()
config.read()
