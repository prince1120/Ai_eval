"""add_stt_segments_quality_and_audio_hash

Adds the Whisper segment payload, transcript quality signals, the STT model
name, and the audio content hash used for upload deduplication.

Revision ID: b7c2e1f04a83
Revises: 'eabb9eaa4fcc'
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c2e1f04a83'
down_revision: Union[str, None] = 'eabb9eaa4fcc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transcripts', sa.Column('segments', sa.JSON(), nullable=True))
    op.add_column('transcripts', sa.Column('stt_confidence', sa.Float(), nullable=True))
    op.add_column('transcripts', sa.Column('stt_quality_flags', sa.JSON(), nullable=True))
    op.add_column('transcripts', sa.Column('stt_model', sa.String(length=100), nullable=True))
    op.add_column('transcripts', sa.Column('audio_sha256', sa.String(length=64), nullable=True))
    # Dedup lookups are always scoped to one organization, so the index is
    # composite rather than a global unique constraint on the hash.
    op.create_index(
        'idx_transcripts_org_audio_sha256',
        'transcripts',
        ['organization_id', 'audio_sha256'],
    )


def downgrade() -> None:
    op.drop_index('idx_transcripts_org_audio_sha256', table_name='transcripts')
    op.drop_column('transcripts', 'audio_sha256')
    op.drop_column('transcripts', 'stt_model')
    op.drop_column('transcripts', 'stt_quality_flags')
    op.drop_column('transcripts', 'stt_confidence')
    op.drop_column('transcripts', 'segments')
