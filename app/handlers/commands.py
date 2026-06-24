"""Telegram command handlers for the MVP bot flow."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.handlers.states import VacancyFlow
from app.services.bot_responses import (
    format_cover_letter_response,
    format_vacancy_analysis_response,
    get_analyze_vacancy_prompt,
    get_cover_letter_prompt,
    get_help_text,
    get_start_text,
)
from app.services.cover_letter_generator import generate_cover_letter
from app.services.vacancy_analyzer import analyze_vacancy

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
async def analyze_vacancy_text(message: Message, state: FSMContext) -> None:
    """Analyze the vacancy text sent after /analyze_vacancy."""
    vacancy_text = message.text or ""
    analysis = analyze_vacancy(vacancy_text)

    await state.clear()
    await message.answer(format_vacancy_analysis_response(analysis))


@router.message(VacancyFlow.waiting_for_cover_letter_text)
async def generate_cover_letter_text(message: Message, state: FSMContext) -> None:
    """Generate a cover letter draft after /generate_cover_letter."""
    vacancy_text = message.text or ""
    cover_letter = generate_cover_letter(vacancy_text)

    await state.clear()
    await message.answer(format_cover_letter_response(cover_letter))
