from alembic import op
import sqlalchemy as sa

revision = "0006_rate_precision"
down_revision = "0005_loans"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("rates") as b:
        b.alter_column(
            "annual_rate_percent",
            existing_type=sa.Numeric(8, 4),
            type_=sa.Numeric(12, 6),
            existing_nullable=False,
        )

def downgrade():
    with op.batch_alter_table("rates") as b:
        b.alter_column(
            "annual_rate_percent",
            existing_type=sa.Numeric(12, 6),
            type_=sa.Numeric(8, 4),
            existing_nullable=False,
        )