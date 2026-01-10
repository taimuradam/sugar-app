"""loans

Revision ID: 0005_loans
Revises: 0004_kibor_unique_rates
Create Date: 2026-01-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_loans"
down_revision = "0004_kibor_unique_rates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bank_id", sa.Integer(), sa.ForeignKey("banks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kibor_tenor_months", sa.Integer(), nullable=False),
        sa.Column("additional_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("kibor_placeholder_rate_percent", sa.Numeric(8, 4), nullable=False, server_default="0.0"),
        sa.Column("max_loan_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("bank_id", "name", name="uq_loans_bank_name"),
    )
    op.create_index("ix_loans_bank_id", "loans", ["bank_id"])

    op.add_column("transactions", sa.Column("loan_id", sa.Integer(), nullable=True))
    op.create_index("ix_transactions_loan_id", "transactions", ["loan_id"])
    op.create_foreign_key("fk_transactions_loan_id", "transactions", "loans", ["loan_id"], ["id"], ondelete="SET NULL")

    op.execute(
        sa.text(
            """
            WITH latest_settings AS (
              SELECT DISTINCT ON (bank_id)
                bank_id,
                kibor_tenor_months,
                additional_rate,
                kibor_placeholder_rate_percent,
                max_loan_amount
              FROM bank_settings
              ORDER BY bank_id, year DESC
            )
            INSERT INTO loans (bank_id, name, kibor_tenor_months, additional_rate, kibor_placeholder_rate_percent, max_loan_amount)
            SELECT
              b.id,
              'Default Loan',
              COALESCE(ls.kibor_tenor_months, 1),
              ls.additional_rate,
              COALESCE(ls.kibor_placeholder_rate_percent, 0),
              ls.max_loan_amount
            FROM banks b
            LEFT JOIN latest_settings ls ON ls.bank_id = b.id
            WHERE NOT EXISTS (SELECT 1 FROM loans l WHERE l.bank_id = b.id);
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE transactions t
            SET loan_id = l.id
            FROM loans l
            WHERE t.bank_id = l.bank_id
              AND l.name = 'Default Loan'
              AND t.loan_id IS NULL;
            """
        )
    )


def downgrade():
    op.drop_constraint("fk_transactions_loan_id", "transactions", type_="foreignkey")
    op.drop_index("ix_transactions_loan_id", table_name="transactions")
    op.drop_column("transactions", "loan_id")
    op.drop_index("ix_loans_bank_id", table_name="loans")
    op.drop_table("loans")
