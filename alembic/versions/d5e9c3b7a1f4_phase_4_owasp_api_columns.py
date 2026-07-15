"""phase-4 owasp api columns

Adds (additive, no backfill):
  * engagements.assessment_profile (default 'general')
  * engagements.api_spec_ref (nullable)
  * findings.owasp_api_ref (nullable)

Revision ID: d5e9c3b7a1f4
Revises: c4d8f1a9b2e7
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e9c3b7a1f4'
down_revision: Union[str, None] = 'c4d8f1a9b2e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'engagements',
        sa.Column(
            'assessment_profile',
            sa.Text(),
            nullable=True,
            server_default=sa.text("'general'"),
        ),
    )
    op.add_column(
        'engagements',
        sa.Column('api_spec_ref', sa.Text(), nullable=True),
    )
    op.add_column(
        'findings',
        sa.Column('owasp_api_ref', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('findings', 'owasp_api_ref')
    op.drop_column('engagements', 'api_spec_ref')
    op.drop_column('engagements', 'assessment_profile')
