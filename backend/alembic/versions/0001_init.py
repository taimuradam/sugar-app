from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "banks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("bank_type", sa.String(length=16), nullable=False),
        sa.Column("additional_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_banks_name", "banks", ["name"], unique=True)

    op.create_table(
        "rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bank_id", sa.Integer(), sa.ForeignKey("banks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("annual_rate_percent", sa.Numeric(12, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_rates_bank_id", "rates", ["bank_id"], unique=False)
    op.create_index("ix_rates_effective_date", "rates", ["effective_date"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bank_id", sa.Integer(), sa.ForeignKey("banks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False, server_default="principal"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_transactions_bank_id", "transactions", ["bank_id"], unique=False)
    op.create_index("ix_transactions_date", "transactions", ["date"], unique=False)

def downgrade():
    op.drop_index("ix_transactions_date", table_name="transactions")
    op.drop_index("ix_transactions_bank_id", table_name="transactions")
    op.drop_table("transactions")

    op.drop_index("ix_rates_effective_date", table_name="rates")
    op.drop_index("ix_rates_bank_id", table_name="rates")
    op.drop_table("rates")

    op.drop_index("ix_banks_name", table_name="banks")
    op.drop_table("banks")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
