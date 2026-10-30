"""template aware architecture and verification schema

Revision ID: a1b2c3d4e5f6
Revises: f4f1a251fbae
Create Date: 2026-10-30 20:20:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f4f1a251fbae'
branch_labels = None
depends_on = None

def upgrade():
    # 1. User table extensions
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('full_name', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('password_hash', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('phone_verified', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('account_status', sa.String(length=30), server_default='active', nullable=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))

    # 2. Verifications table
    op.create_table(
        'verifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('identifier', sa.String(length=254), nullable=False),
        sa.Column('verification_type', sa.String(length=30), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('verifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_verifications_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_verifications_identifier'), ['identifier'], unique=False)
        batch_op.create_index(batch_op.f('ix_verifications_verification_type'), ['verification_type'], unique=False)

    # 3. Template table extensions
    with op.batch_alter_table('templates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('template_name', sa.String(length=120), server_default='', nullable=False))
        batch_op.add_column(sa.Column('template_type', sa.String(length=30), server_default='built_in', nullable=False))
        batch_op.add_column(sa.Column('original_file_path', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('analysis_status', sa.String(length=30), server_default='analyzed', nullable=False))
        batch_op.add_column(sa.Column('is_confirmed', sa.Boolean(), server_default='1', nullable=False))
        batch_op.add_column(sa.Column('created_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
        batch_op.create_foreign_key('fk_templates_user_id', 'users', ['created_by_user_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_templates_created_by_user_id'), ['created_by_user_id'], unique=False)

    # 4. Resume table extensions
    with op.batch_alter_table('resumes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('collection_status', sa.String(length=30), server_default='uploaded', nullable=False))
        batch_op.add_column(sa.Column('generation_status', sa.String(length=30), server_default='pending', nullable=False))
        batch_op.add_column(sa.Column('validation_report', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
        batch_op.create_index(batch_op.f('ix_resumes_collection_status'), ['collection_status'], unique=False)
        batch_op.create_index(batch_op.f('ix_resumes_generation_status'), ['generation_status'], unique=False)

    # 5. Resume Answers table
    op.create_table(
        'resume_answers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resume_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('field_path', sa.String(length=120), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer_value', sa.JSON(), nullable=False),
        sa.Column('confirmed', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('resume_answers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_resume_answers_resume_id'), ['resume_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_resume_answers_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_resume_answers_field_path'), ['field_path'], unique=False)

    # 6. Generated Documents table
    op.create_table(
        'generated_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resume_id', sa.Integer(), nullable=False),
        sa.Column('docx_path', sa.Text(), nullable=True),
        sa.Column('pdf_path', sa.Text(), nullable=True),
        sa.Column('template_id', sa.String(length=60), nullable=False),
        sa.Column('template_version', sa.String(length=30), server_default='1.0.0', nullable=False),
        sa.Column('validation_result', sa.JSON(), nullable=False),
        sa.Column('quality_score', sa.Integer(), server_default='100', nullable=False),
        sa.Column('is_valid', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('generated_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_generated_documents_resume_id'), ['resume_id'], unique=False)

def downgrade():
    op.drop_table('generated_documents')
    op.drop_table('resume_answers')
    with op.batch_alter_table('resumes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_resumes_generation_status'))
        batch_op.drop_index(batch_op.f('ix_resumes_collection_status'))
        batch_op.drop_column('updated_at')
        batch_op.drop_column('validation_report')
        batch_op.drop_column('generation_status')
        batch_op.drop_column('collection_status')
    with op.batch_alter_table('templates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_templates_created_by_user_id'))
        batch_op.drop_constraint('fk_templates_user_id', type_='foreignkey')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_by_user_id')
        batch_op.drop_column('is_confirmed')
        batch_op.drop_column('analysis_status')
        batch_op.drop_column('original_file_path')
        batch_op.drop_column('template_type')
        batch_op.drop_column('template_name')
    op.drop_table('verifications')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('account_status')
        batch_op.drop_column('phone_verified')
        batch_op.drop_column('email_verified')
        batch_op.drop_column('password_hash')
        batch_op.drop_column('phone')
        batch_op.drop_column('full_name')

