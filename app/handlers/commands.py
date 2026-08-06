"""Telegram command handlers for the MVP bot flow."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, Update

from app.core.errors import USER_ERROR_MESSAGES, ErrorCategory, WorkflowError
from app.db.models import WorkflowStatus
from app.handlers.states import VacancyFlow
from app.schemas.vacancy import VacancyAnalysis
from app.services.bot_responses import (
    format_cover_letter_response,
    format_vacancy_analysis_response,
    get_analyze_vacancy_prompt,
    get_cover_letter_prompt,
    get_help_text,
    get_start_text,
)
from app.services.workflow_service import WorkflowService

router = Router()


@router.message(Command("start"))
async def start_command(message: Message) -> None:
    """Introduce the bot to the user."""
    await message.answer(get_start_text())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    """Show available bot commands."""
    await message.answer(get_help_text())


@router.message(Command("analyze_vacancy"))
async def analyze_vacancy_command(message: Message, state: FSMContext) -> None:
    """Ask the user to send vacancy text for deterministic analysis."""
    await state.set_state(VacancyFlow.waiting_for_analysis_text)
    await message.answer(get_analyze_vacancy_prompt())


@router.message(Command("generate_cover_letter"))
async def generate_cover_letter_command(message: Message, state: FSMContext) -> None:
    """Ask the user to send vacancy text for cover letter generation."""
    await state.set_state(VacancyFlow.waiting_for_cover_letter_text)
    await message.answer(get_cover_letter_prompt())


@router.message(VacancyFlow.waiting_for_analysis_text)
async def analyze_vacancy_text(
    message: Message,
    state: FSMContext,
    event_update: Update,
    workflow_service: WorkflowService,
) -> None:
    """Pass vacancy text and minimal identifiers to the durable service."""
    identifiers = _get_identifiers(message, event_update)
    if identifiers is None:
        await state.clear()
        await message.answer(USER_ERROR_MESSAGES[ErrorCategory.INVALID_INPUT])
        return
    user_id, chat_id, update_id = identifiers
    try:
        outcome = await workflow_service.analyze_vacancy(
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            telegram_update_id=update_id,
            vacancy_text=message.text or "",
        )
        response = _format_workflow_outcome(outcome)
    except WorkflowError as error:
        response = error.user_message
    await state.clear()
    await message.answer(response)


@router.message(VacancyFlow.waiting_for_cover_letter_text)
async def generate_cover_letter_text(
    message: Message,
    state: FSMContext,
    event_update: Update,
    workflow_service: WorkflowService,
) -> None:
    """Pass cover-letter context and minimal identifiers to the durable service."""
    identifiers = _get_identifiers(message, event_update)
    if identifiers is None:
        await state.clear()
        await message.answer(USER_ERROR_MESSAGES[ErrorCategory.INVALID_INPUT])
        return
    user_id, chat_id, update_id = identifiers
    try:
        outcome = await workflow_service.generate_cover_letter(
            telegram_user_id=user_id,
            telegram_chat_id=chat_id,
            telegram_update_id=update_id,
            vacancy_text=message.text or "",
        )
        response = _format_workflow_outcome(outcome)
    except WorkflowError as error:
        response = error.user_message
    await state.clear()
    await message.answer(response)


def _get_identifiers(
    message: Message, event_update: Update
) -> tuple[int, int, int] | None:
    """Extract only the identity and idempotency fields needed by the service."""
    if message.from_user is None:
        return None
    return message.from_user.id, message.chat.id, event_update.update_id


def _format_workflow_outcome(outcome: object) -> str:
    """Render persisted safe results or stable domain errors."""
    from app.schemas.workflow import WorkflowOutcome

    if not isinstance(outcome, WorkflowOutcome):
        return USER_ERROR_MESSAGES[ErrorCategory.INTERNAL_ERROR]
    if outcome.error_category is not None:
        return USER_ERROR_MESSAGES[outcome.error_category]
    if outcome.status != WorkflowStatus.COMPLETED or outcome.result is None:
        return USER_ERROR_MESSAGES[ErrorCategory.DUPLICATE_UPDATE]
    if outcome.operation.value == "vacancy_analysis":
        analysis = VacancyAnalysis.model_validate(outcome.result["analysis"])
        return format_vacancy_analysis_response(analysis)
    cover_letter = str(outcome.result["cover_letter"]["text"])
    return format_cover_letter_response(cover_letter)
