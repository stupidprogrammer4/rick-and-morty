from papilio.errors.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)


def missing(entity: str, id: int | str) -> NotFoundException:
    return NotFoundException(
        message="مورد پیدا نشد.",
        message_code=f"{entity}_not_found",
        entity=entity,
        identifier="id",
        identifier_value=id,
    )


def conflict(message: str) -> ConflictException:
    return ConflictException(
        message=message, message_code="invalid_state", unique_dict={}
    )


def forbidden() -> ForbiddenException:
    return ForbiddenException(
        message="دسترسی مجاز نیست.", message_code="owner_required"
    )
