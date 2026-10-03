from papilio.types.enums import FaStrEnum


class SourceSwitch(FaStrEnum):
    SUPPLIER = ("supplier", "تأمین‌کننده")
    GLOBAL_MARKET = ("global_market", "بازار جهانی")
    IRAN_MARKET = ("iran_market", "بازار ایران")


class SourceUpdateType(FaStrEnum):
    SCHEDULER = ("scheduler", "زمان‌بندی‌شده")
    EVENT = ("event", "رویدادی")


class ErrorType(FaStrEnum):
    LOGICAL_ERROR = ("logical", "خطای منطقی")
    HTTP_ERROR = ("http", "خطای ارتباط")


class SourceCode(FaStrEnum):
    DIGIKALA = ("digikala", "دیجی‌کالا")
    GOLDIKA = ("goldika", "گلدیکا")
    MELIGOLD = ("meligold", "ملی‌گلد")
    MILIGOLD = ("miligold", "میلی‌گلد")
    HANZAEI = ("hanzaei", "حنزایی")
    MIRROKNI = ("mirrokni", "میررکنی")
    NOGHRESEA = ("noghresea", "نقره‌سی")
    TALALAND = ("talaland", "طلالند")
    TALASEA = ("talasea", "طلاسی")
    TALINE = ("taline", "طلاین")
    TECHNOGOLD = ("technogold", "تکنوگلد")
    WALLGOLD = ("wallgold", "والگلد")

    ALANCHAND = ("alanchand", "الان‌چند")
    ESTJT = ("estjt", "ای‌اس‌تی‌جی‌تی")
    TGJU = ("tgju", "تی‌جی‌جی‌یو")
    WALLEX = ("wallex", "والکس")

    GOLD_API = ("gold_api", "گلد‌ای‌پی‌آی")
    GOLDPRICE_DEV = ("goldprice_dev", "گلدپرایس")


class SourceSortBy(FaStrEnum):
    CREATED_AT = ("created_at", "تاریخ ثبت")
    TITLE = ("title", "عنوان")


class SelectionReason(FaStrEnum):
    CLOSED_MARKET = ("closed_market", "بازار بسته")
    OUTLIER = ("outlier", "پرت")
    SWITCH_OFF = ("switch_off", "خاموش")
