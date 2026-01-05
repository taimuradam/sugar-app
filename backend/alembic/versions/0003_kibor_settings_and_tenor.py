from alembic import op
import sqlalchemy as sa

revision = "0003_kibor_settings_and_tenor"
down_revision = "0002_audit_logs"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("rates", sa.Column("tenor_months", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_rates_tenor_months", "rates", ["tenor_months"], unique=False)

    op.create_table(
        "bank_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bank_id", sa.Integer(), sa.ForeignKey("banks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("kibor_tenor_months", sa.Integer(), nullable=False),
        sa.Column("additional_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("kibor_placeholder_rate_percent", sa.Numeric(8, 4), nullable=False),
        sa.Column("max_loan_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.UniqueConstraint("bank_id", "year", name="uq_bank_settings_bank_year"),
    )
    op.create_index("ix_bank_settings_bank_id", "bank_settings", ["bank_id"], unique=False)
    op.create_index("ix_bank_settings_year", "bank_settings", ["year"], unique=False)

def downgrade():
    op.drop_index("ix_bank_settings_year", table_name="bank_settings")
    op.drop_index("ix_bank_settings_bank_id", table_name="bank_settings")
    op.drop_table("bank_settings")

    op.drop_index("ix_rates_tenor_months", table_name="rates")
    op.drop_column("rates", "tenor_months")
