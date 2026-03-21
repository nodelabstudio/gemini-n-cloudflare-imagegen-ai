"""Lightweight schema migrations. Runs idempotent ALTER TABLE statements on startup."""

from sqlalchemy import inspect, text


def apply_migrations(engine):
    insp = inspect(engine)

    # --- images table ---
    if "images" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("images")}

        if "is_favorite" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE images ADD COLUMN is_favorite BOOLEAN DEFAULT 0 NOT NULL"))

        if "share_token" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE images ADD COLUMN share_token VARCHAR(32)"))

        if "is_public" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE images ADD COLUMN is_public BOOLEAN DEFAULT 0 NOT NULL"))

    # --- image_tags table ---
    if "image_tags" not in insp.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE image_tags (
                    id VARCHAR PRIMARY KEY,
                    image_id VARCHAR NOT NULL,
                    tag VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX ix_image_tags_image_id ON image_tags (image_id)"))
            conn.execute(text("CREATE INDEX ix_image_tags_tag ON image_tags (tag)"))
