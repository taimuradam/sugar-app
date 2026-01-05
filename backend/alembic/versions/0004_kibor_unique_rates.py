"""Add unique constraint for daily KIBOR rates.

Revision ID: 0004_kibor_unique_rates
Revises: 0003_kibor_settings_and_tenor
Create Date: 2026-01-06
"""

from alembic import op


revision = "0004_kibor_unique_rates"
down_revision = "0003_kibor_settings_and_tenor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_rates_bank_tenor_effective_date",
        "rates",
        ["bank_id", "tenor_months", "effective_date"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_rates_bank_tenor_effective_date", "rates", type_="unique")
