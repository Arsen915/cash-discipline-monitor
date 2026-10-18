"""Каталог распознаваемых типов нарушений и их нормативных оснований (акты НБРК, adilet.zan.kz).

Цитаты в поле ``requirement`` сверены с текстом актов; если пункт передан кратко,
это пересказ, а не дословная цитата. Ссылки ведут на официальную базу «Әділет».
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormativeDocument:
    key: str
    title: str
    act: str
    short: str
    url: str


@dataclass(frozen=True)
class ViolationType:
    code: str
    title: str
    document: NormativeDocument
    clause: str
    requirement: str
    detects: str

    def rule_dict(self) -> dict:
        return {
            "document": self.document.title,
            "act": self.document.act,
            "clause": self.clause,
            "requirement": self.requirement,
            "url": self.document.url,
        }

    def basis_sentence(self) -> str:
        return f"Основание: {self.document.short}, {self.clause}."


CASH_OPERATIONS_RULES = NormativeDocument(
    key="nbrk-231",
    title=(
        "Правила осуществления кассовых операций и операций по инкассации банкнот, монет и "
        "ценностей в банках второго уровня, филиалах банков-нерезидентов Республики Казахстан, "
        "Национальном операторе почты и юридических лицах, исключительной деятельностью которых "
        "является инкассация банкнот, монет и ценностей"
    ),
    act=(
        "Утверждены постановлением Правления Национального Банка Республики Казахстан "
        "от 29 ноября 2019 года № 231 (зарегистрировано в МЮ РК 3 декабря 2019 года № 19680)"
    ),
    short="Правила кассовых операций и инкассации (пост. Правления НБРК от 29.11.2019 № 231)",
    url="https://adilet.zan.kz/rus/docs/V1900019680",
)

PREMISES_SECURITY_RULES = NormativeDocument(
    key="nbrk-14",
    title=(
        "Правила организации охраны и устройства помещений банков второго уровня, филиалов "
        "банков-нерезидентов Республики Казахстан, Национального оператора почты, юридических лиц, "
        "исключительной деятельностью которых является инкассация банкнот, монет и ценностей, и "
        "юридических лиц, осуществляющих деятельность исключительно через обменные пункты"
    ),
    act=(
        "Утверждены постановлением Правления Национального Банка Республики Казахстан "
        "от 24 февраля 2020 года № 14 (зарегистрировано в МЮ РК 27 февраля 2020 года № 20075)"
    ),
    short="Правила охраны и устройства помещений банков (пост. Правления НБРК от 24.02.2020 № 14)",
    url="https://adilet.zan.kz/rus/docs/V2000020075",
)


WORKPLACE_ABANDONED = ViolationType(
    code="WORKPLACE_ABANDONED",
    title="Кассир покинул рабочее место во время обслуживания клиента",
    document=CASH_OPERATIONS_RULES,
    clause="п. 22",
    requirement=(
        "«Кассовому работнику не допускается покидать рабочее место до окончания "
        "обслуживания клиента.»"
    ),
    detects="Рабочее место кассира пустует, в то время как клиент остаётся у стойки.",
)

CASH_UNATTENDED = ViolationType(
    code="CASH_UNATTENDED",
    title="Ценности оставлены без присмотра на рабочем месте кассира",
    document=CASH_OPERATIONS_RULES,
    clause="п. 20",
    requirement=(
        "Ранее принятые наличные деньги хранятся в специальных устройствах на рабочем месте "
        "кассира, а не остаются открыто на столе (пересказ п. 20)."
    ),
    detects=(
        "Кассир отсутствует на рабочем месте, а на столе остаются предметы, которых нет "
        "в контрольном кадре пустого стола."
    ),
)

UNAUTHORIZED_PERSON = ViolationType(
    code="UNAUTHORIZED_PERSON",
    title="Посторонний в зоне кассира",
    document=PREMISES_SECURITY_RULES,
    clause="п. 8, пп. 1) п. 16",
    requirement=(
        "Кассовый узел изолируется от других помещений и имеет один закрывающийся служебный вход; "
        "каждая касса имеет отдельный вход с закрывающейся на замок дверью (пересказ)."
    ),
    detects=(
        "Человек из клиентской зоны переходит за стойку, либо за стойкой длительно "
        "находятся несколько человек."
    ),
)

MOBILE_PHONE = ViolationType(
    code="MOBILE_PHONE",
    title="Мобильный телефон в зоне кассира",
    document=CASH_OPERATIONS_RULES,
    clause="п. 12",
    requirement=(
        "«Допускается внос работниками банка в кассовый узел лекарственных средств, медицинских "
        "изделий и средств связи, не имеющих функции фото и видео фиксации.»"
    ),
    detects="Смартфон/мобильный телефон в руках кассира или на рабочем месте за стойкой.",
)

PERSONAL_BELONGINGS = ViolationType(
    code="PERSONAL_BELONGINGS",
    title="Личные вещи в зоне кассира",
    document=CASH_OPERATIONS_RULES,
    clause="п. 12",
    requirement=(
        "«Хранение личных вещей, наличных денег и ценностей работников банка осуществляется "
        "вне кассового узла»"
    ),
    detects="Сумка или рюкзак длительно находится за стойкой на рабочем месте кассира.",
)

CAMERA_OBSTRUCTION = ViolationType(
    code="CAMERA_OBSTRUCTION",
    title="Перекрыт обзор камеры видеонаблюдения кассы",
    document=PREMISES_SECURITY_RULES,
    clause="пп. 6) п. 16",
    requirement=(
        "Касса оборудуется видеокамерами системы видеонаблюдения; перекрытие объектива лишает "
        "кассовые операции видеоконтроля (пересказ)."
    ),
    detects="Кадр становится однородным/тёмным или большая его часть закрыта предметом.",
)

CATALOG: tuple[ViolationType, ...] = (
    WORKPLACE_ABANDONED,
    CASH_UNATTENDED,
    UNAUTHORIZED_PERSON,
    MOBILE_PHONE,
    PERSONAL_BELONGINGS,
    CAMERA_OBSTRUCTION,
)


def catalog_as_dict() -> list[dict]:
    return [
        {"code": v.code, "type": v.title, "detects": v.detects, "rule": v.rule_dict()}
        for v in CATALOG
    ]
