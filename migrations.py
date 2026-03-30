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

        if "image_url" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE images ADD COLUMN image_url VARCHAR(500)"))

        # Make image_data nullable (images now stored in Cloudinary)
        if "image_data" in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE images ALTER COLUMN image_data DROP NOT NULL"))

    # --- users table ---
    if "users" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("users")}
        if "email" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(200)"))

    # --- password_reset_tokens table ---
    if "password_reset_tokens" not in insp.get_table_names():
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE password_reset_tokens (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    token VARCHAR(64) NOT NULL UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT 0 NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX ix_prt_user_id ON password_reset_tokens (user_id)"))
            conn.execute(text("CREATE INDEX ix_prt_token ON password_reset_tokens (token)"))

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
