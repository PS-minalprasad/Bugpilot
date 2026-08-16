"""live_sprints_and_reopen_tracking

Revision ID: b5fbe0948c21
Revises: a4ead0938a56
Create Date: 2026-08-15 11:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5fbe0948c21'
down_revision: Union[str, Sequence[str], None] = 'a4ead0938a56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create sprints table
    op.create_table(
        'sprints',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.String(length=64), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sprints_id'), 'sprints', ['id'], unique=False)
    op.create_index(op.f('ix_sprints_organization_id'), 'sprints', ['organization_id'], unique=False)

    # 2. Add columns to issues
    op.add_column('issues', sa.Column('sprint_id', sa.String(length=64), nullable=True))
    op.add_column('issues', sa.Column('reopen_count', sa.Integer(), server_default='0', nullable=False))
    op.create_index(op.f('ix_issues_sprint_id'), 'issues', ['sprint_id'], unique=False)
    op.create_foreign_key('fk_issues_sprint_id_sprints', 'issues', 'sprints', ['sprint_id'], ['id'], ondelete='SET NULL')

    # 3. Drop legacy jira_connections table if present
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'jira_connections' in inspector.get_table_names():
        op.drop_table('jira_connections')


def downgrade() -> None:
    op.drop_constraint('fk_issues_sprint_id_sprints', 'issues', type_='foreignkey')
    op.drop_index(op.f('ix_issues_sprint_id'), table_name='issues')
    op.drop_column('issues', 'reopen_count')
    op.drop_column('issues', 'sprint_id')
    op.drop_index(op.f('ix_sprints_organization_id'), table_name='sprints')
    op.drop_index(op.f('ix_sprints_id'), table_name='sprints')
    op.drop_table('sprints')
