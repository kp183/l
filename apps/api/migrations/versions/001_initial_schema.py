"""initial_schema

Revision ID: 001
Revises:
Create Date: 2026-05-23

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── organizations ─────────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clerk_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clerk_id", name="uq_users_clerk_id"),
    )
    op.create_index("idx_users_clerk_id", "users", ["clerk_id"])

    # ── org_members ───────────────────────────────────────────────────────────
    op.create_table(
        "org_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "user_id", name="uq_org_members_org_user"),
    )
    op.create_index("idx_org_members_user_id", "org_members", ["user_id"])
    op.create_index("idx_org_members_org_id", "org_members", ["org_id"])

    # ── projects ──────────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_projects_org_id", "projects", ["org_id"])

    # ── api_keys ──────────────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("idx_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("idx_api_keys_project_id", "api_keys", ["project_id"])
    op.create_index(
        "idx_api_keys_active",
        "api_keys",
        ["key_hash"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # ── traces ────────────────────────────────────────────────────────────────
    op.create_table(
        "traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger, nullable=True),
        sa.Column("span_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.BigInteger, nullable=True),
        sa.Column("input_tokens", sa.BigInteger, nullable=True),
        sa.Column("output_tokens", sa.BigInteger, nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'error')", name="ck_traces_status"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_traces_project_started", "traces", ["project_id", "started_at"]
    )
    op.create_index("idx_traces_status", "traces", ["status"])

    # ── spans ─────────────────────────────────────────────────────────────────
    op.create_table(
        "spans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_span_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("span_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger, nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("tool_name", sa.String(255), nullable=True),
        sa.Column("tool_call_id", sa.String(255), nullable=True),
        sa.Column("input", postgresql.JSONB, nullable=True),
        sa.Column("output", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=True),
        sa.Column("error_type", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("error_stack", sa.Text, nullable=True),
        sa.Column("payload_url", sa.Text, nullable=True),
        sa.CheckConstraint(
            "span_type IN ('llm', 'tool', 'agent', 'custom')",
            name="ck_spans_span_type",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'error')", name="ck_spans_status"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_spans_trace_started", "spans", ["trace_id", "started_at"])
    op.create_index("idx_spans_project_id", "spans", ["project_id"])
    op.create_index(
        "idx_spans_tags_gin",
        "spans",
        ["tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_table("spans")
    op.drop_table("traces")
    op.drop_table("api_keys")
    op.drop_table("projects")
    op.drop_table("org_members")
    op.drop_table("users")
    op.drop_table("organizations")
