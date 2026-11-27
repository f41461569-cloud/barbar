"""registration v2 user model

Revision ID: 3c0fb3fec533
Revises: cc9ac3ac14f8
Create Date: 2026-11-27 20:09:39.185546

Adds the nullable profile columns from ADR 007, makes ``users.phone`` nullable
(admins register without a phone), and adds the uniqueness indexes the service
relies on. Additive and safe to run before deploying the new app code.

Downgrade restores ``phone NOT NULL``, so it fails if any v2 admin still has a
NULL phone. Delete those admin accounts or assign them a phone first.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c0fb3fec533'
down_revision: Union[str, None] = 'cc9ac3ac14f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('national_id', sa.String(length=10), nullable=True))
    op.add_column('users', sa.Column('license_number', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('truck_type', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('plate_number', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('cargo_type_preference', sa.String(length=20), nullable=True))

    # batch_alter_table keeps this migration valid on SQLite as well as PostgreSQL.
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'phone', existing_type=sa.String(length=20), nullable=True
        )

    op.create_index('ix_users_license_number', 'users', ['license_number'], unique=True)
    op.create_index('ix_users_national_id', 'users', ['national_id'], unique=True)
    op.create_index('ix_users_plate_number', 'users', ['plate_number'], unique=False)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_plate_number', table_name='users')
    op.drop_index('ix_users_national_id', table_name='users')
    op.drop_index('ix_users_license_number', table_name='users')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('cargo_type_preference')
        batch_op.drop_column('plate_number')
        batch_op.drop_column('truck_type')
        batch_op.drop_column('license_number')
        batch_op.drop_column('national_id')
        batch_op.drop_column('username')
        # Fails while a v2 admin row still has phone IS NULL; see the docstring.
        batch_op.alter_column(
            'phone', existing_type=sa.String(length=20), nullable=False
        )
