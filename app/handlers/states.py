"""FSM states for multi-step vacancy flows."""

from aiogram.fsm.state import State, StatesGroup


class VacancyFlow(StatesGroup):
    """States for vacancy analysis and cover letter generation."""

    waiting_for_analysis_text = State()
    waiting_for_cover_letter_text = State()
